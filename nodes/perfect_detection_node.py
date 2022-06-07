import time

from carla import Client
from pylot.simulation.utils import extract_data_in_pylot_format

from dora_tracing import extract_context, tracer
from dora_watermark import dump, load

CARLA_SIMULATOR_HOST = "localhost"
CARLA_SIMULATOR_PORT = "2000"

client = Client(CARLA_SIMULATOR_HOST, int(CARLA_SIMULATOR_PORT))
client.set_timeout(30.0)  # seconds
world = client.get_world()

town_name = world.get_map().name
DYNAMIC_OBSTACLE_DISTANCE_THRESHOLD = 500


def dora_run(inputs):
    keys = inputs.keys()

    if (
        "position" not in keys
        or "segmented_frame" not in keys
        or "depth_frame" not in keys
    ):
        return {}

    context = extract_context(inputs)
    with tracer.start_span(
        f"python-{__name__}-pickle-parsing", context=context
    ):
        pose = load(inputs, "position")
        vehicle_transform = pose.transform

        depth_frame = load(inputs, "depth_frame")
        segmented_frame = load(inputs, "segmented_frame")

    actor_list = world.get_actors()
    (vehicles, people, _traffic_lights, _, _) = extract_data_in_pylot_format(
        actor_list
    )
    det_obstacles = []
    for obstacle in vehicles + people:
        # Calculate the distance of the obstacle from the vehicle, and
        # convert to camera view if it is less than
        # dynamic_obstacle_distance_threshold metres away.
        if (
            obstacle.transform.location.distance(vehicle_transform.location)
            <= DYNAMIC_OBSTACLE_DISTANCE_THRESHOLD
        ):
            bbox = obstacle.populate_bounding_box_2D(
                depth_frame, segmented_frame
            )
            if bbox:
                det_obstacles.append(obstacle)

    context = extract_context(inputs)
    with tracer.start_span(
        f"python-{__name__}-pickle-parsing", context=context
    ):
        byte_array = dump(det_obstacles)

    return {
        "obstacles_without_location": byte_array,
        #   "traffic_lights": dump(visible_tls),
    }
