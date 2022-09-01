from typing import Callable

import cv2
import numpy as np
import torch
from strong_sort import StrongSORT

from dora_utils import DoraStatus


def xxyy2xywh(x):
    # Convert nx4 boxes from [x1, y1, x2, y2] to [x, y, w, h] where xy1=top-left, xy2=bottom-right
    y = x.clone() if isinstance(x, torch.Tensor) else np.copy(x)
    y[:, 0] = (x[:, 0] + x[:, 1]) / 2  # x center
    y[:, 1] = (x[:, 2] + x[:, 3]) / 2  # y center
    y[:, 2] = x[:, 1] - x[:, 0]  # width
    y[:, 3] = x[:, 3] - x[:, 2]  # height
    return y


class Operator:
    """
    Infering object from images
    """

    def __init__(self):
        model = StrongSORT(
            "osnet_x0_25_msmt17.pt",
            torch.device("cuda"),
            False,
        )
        model.model.warmup()
        self.model = model
        self.frame = []

    def on_input(
        self,
        input_id: str,
        value: bytes,
        send_output: Callable[[str, bytes], None],
    ) -> DoraStatus:

        if input_id == "image":
            frame = cv2.imdecode(
                np.frombuffer(
                    value[24:],
                    dtype="uint8",
                ),
                -1,
            )

            self.frame = frame[:, :, :3]
            return DoraStatus.CONTINUE

        if input_id == "obstacles_bb" and len(self.frame) != 0:
            obstacles = np.frombuffer(value, dtype="int32").reshape((-1, 6))
            if obstacles.shape[0] == 1:
                self.model.increment_ages()
                send_output("obstacles_id", np.array([]).tobytes())
                return DoraStatus.CONTINUE

            # Post Processing yolov5
            xywhs = xxyy2xywh(obstacles[:, 0:4])
            confs = obstacles[:, 4]
            clss = obstacles[:, 5]
            with torch.no_grad():
                outputs = np.array(
                    self.model.update(xywhs, confs, clss, self.frame)
                ).astype("int32")
                if len(outputs) != 0:
                    outputs = outputs[
                        :, [0, 2, 1, 3, 4, 5, 6]
                    ]  # xyxy -> x1, x2, y1, y2 track_id, class_id, conf

                    send_output("obstacles_id", outputs.tobytes())

        return DoraStatus.CONTINUE
