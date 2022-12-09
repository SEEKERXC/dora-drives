import threading
from typing import Callable

import numpy as np

from _dora_utils import DoraStatus
from carla import Client, VehicleControl, command

CARLA_SIMULATOR_HOST = "localhost"
CARLA_SIMULATOR_PORT = "2000"
STEER_GAIN = 0.7
client = Client(CARLA_SIMULATOR_HOST, int(CARLA_SIMULATOR_PORT))
client.set_timeout(30.0)

mutex = threading.Lock()


def radians_to_steer(rad: float, steer_gain: float):
    """Converts radians to steer input.

    Returns:
        :obj:`float`: Between [-1.0, 1.0].
    """
    steer = steer_gain * rad
    if steer > 0:
        steer = min(steer, 1)
    else:
        steer = max(steer, -1)
    return steer


class Operator:
    """
    Execute any `control` it r:ecieve given a `vehicle_id`
    """

    def __init__(self):
        self.vehicle_id = None

    def on_input(
        self,
        dora_input: dict,
        send_output: Callable[[str, bytes], None],
    ):
        """Handle input.
        Args:
            dora_input["id"](str): Id of the input declared in the yaml configuration
            dora_input["data"] (bytes): Bytes message of the input
            send_output (Callable[[str, bytes]]): Function enabling sending output back to dora.
        """

        if self.vehicle_id is None and "vehicle_id" != dora_input["id"]:
            return DoraStatus.CONTINUE
        elif self.vehicle_id is None and "vehicle_id" == dora_input["id"]:
            self.vehicle_id = int.from_bytes(dora_input["data"], "big")
        elif self.vehicle_id is not None and "vehicle_id" == dora_input["id"]:
            return DoraStatus.CONTINUE

        if "control" != dora_input["id"]:
            return DoraStatus.CONTINUE

        control = np.frombuffer(dora_input["data"])

        steer = radians_to_steer(control[2], STEER_GAIN)
        vec_control = VehicleControl(
            throttle=control[0],
            steer=control[1],
            brake=steer,
            hand_brake=False,
            reverse=False,
        )

        client.apply_batch_sync(
            [command.ApplyVehicleControl(self.vehicle_id, vec_control)]
        )
        return DoraStatus.CONTINUE
