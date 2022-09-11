import math
import zlib
from typing import Callable

import cv2
import numpy as np
import open3d as o3d
import torch
from imfnet import (
    extract_features,
    get_model,
    make_open3d_feature_from_numpy,
    make_open3d_point_cloud,
    process_image,
    run_ransac,
)

from dora_utils import DoraStatus


class Operator:
    """
    Infering object from images
    """

    def __init__(self):
        self.model, self.config = get_model()
        self.frame = []
        self.point_cloud = []
        self.previous_pc_down = []
        self.previous_features = []
        self.previous_position = []
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window()

    def on_input(
        self,
        input_id: str,
        value: bytes,
        send_output: Callable[[str, bytes], None],
    ) -> DoraStatus:
        """Handle image
        Args:
            input_id (str): Id of the input declared in the yaml configuration
            value (bytes): Bytes message of the input
            send_output (Callable[[str, bytes]]): Function enabling sending output back to dora.
        """

        if input_id == "lidar_pc":
            point_cloud = np.frombuffer(
                zlib.decompress(value[24:]), dtype=np.dtype("f4")
            )
            point_cloud = np.reshape(
                point_cloud, (int(point_cloud.shape[0] / 4), 4)
            )

            # To camera coordinate
            # The latest coordinate space is the unreal space.
            point_cloud = np.dot(
                point_cloud,
                np.array(
                    [[0, 1, 0, 0], [0, 0, -1, 0], [1, 0, 0, 0], [0, 0, 0, 1]]
                ),
            )

            self.point_cloud = point_cloud[:, :3]
            return DoraStatus.CONTINUE

        if input_id == "image":
            frame = cv2.imdecode(
                np.frombuffer(
                    value[24:],
                    dtype="uint8",
                ),
                -1,
            )
            self.frame = frame[:, :, :3]

        if (
            self.frame.shape[0] != self.config.image_H
            or self.frame.shape[1] != self.config.image_W
        ):
            image = process_image(
                image=self.frame,
                aim_H=self.config.image_H,
                aim_W=self.config.image_W,
            )

        image = np.transpose(image, axes=(2, 0, 1))
        current_image = np.expand_dims(image, axis=0)

        if len(self.point_cloud) == 0:
            return DoraStatus.CONTINUE
        # Extract features
        current_pc_down, current_features = extract_features(
            self.model,
            xyz=self.point_cloud,
            rgb=None,
            normal=None,
            voxel_size=0.025,
            device=torch.device("cuda"),
            skip_check=True,
            image=current_image,
        )

        current_pc_down = make_open3d_point_cloud(current_pc_down)
        current_features = current_features.cpu().detach().numpy()
        current_features = make_open3d_feature_from_numpy(current_features)

        if type(self.previous_features) == list:
            self.previous_pc_down = current_pc_down
            self.previous_features = current_features
            self.vis.add_geometry(current_pc_down)

            return DoraStatus.CONTINUE
        else:
            self.vis.update_geometry(current_pc_down)
            self.vis.poll_events()
            self.vis.update_renderer()

        T = run_ransac(
            self.previous_pc_down,
            current_pc_down,
            self.previous_features,
            current_features,
            0.025,
        )
        pitch_r = math.asin(np.clip(T[2, 0], -1, 1))
        yaw_r = math.acos(np.clip(T[0, 0] / math.cos(pitch_r), -1, 1))
        roll_r = math.asin(np.clip(T[2, 1] / (-1 * math.cos(pitch_r)), -1, 1))
        # Calculation of the angle https://stackoverflow.com/questions/15022630/how-to-calculate-the-angle-from-rotation-matrix

        x, y, z = T[0, 3], T[1, 3], T[2, 3]

        position = np.array(
            [
                x,
                y,
                z,
                math.degrees(pitch_r),
                math.degrees(yaw_r),
                math.degrees(roll_r),
            ],
            dtype=np.float32,
        )
        send_output("relative_position", position.tobytes())

        self.previous_position = position
        self.previous_pc_down = current_pc_down
        self.previous_features = current_features

        return DoraStatus.CONTINUE
