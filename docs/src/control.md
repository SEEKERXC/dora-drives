# Control

Car can simplistically be controlled in general using 3 variables: `throttle, steering, brake`. We're going to focus on those 3 for the moment.

To send a control to a Carla car, we can use `carla_control_op.py` that takes an array of 3 variables: `throttle, steering, brake` and apply it to our car.

To translate out waypoints to those control, we're using a PID controller that is able to adjust the steering according to the response of the steering, and we're going to pipe this response to the CARLA API so that the car can move. The PID controller code is in `pid_control_op.py`.

The full graph look as follows:

```yaml
{{#include ../../graphs/tutorials/carla_full.yaml}}
```

You can visualize your graph with:
```bash
dora graph graphs/tutorials/carla_full.yaml --open                 
 ```

```mermaid
        flowchart TB
  oasis_agent
subgraph carla_gps_op
  carla_gps_op/op[op]
end
subgraph yolov5
  yolov5/op[op]
end
subgraph obstacle_location_op
  obstacle_location_op/op[op]
end
subgraph fot_op
  fot_op/op[op]
end
subgraph pid_control_op
  pid_control_op/op[op]
end
subgraph ___dora___ [dora]
  subgraph ___timer_timer___ [timer]
    dora/timer/secs/1[\secs/1/]
  end
end
  pid_control_op/op -- control --> oasis_agent
  dora/timer/secs/1 -- tick --> oasis_agent
  oasis_agent -- objective_waypoints --> carla_gps_op/op
  oasis_agent -- opendrive --> carla_gps_op/op
  oasis_agent -- position --> carla_gps_op/op
  oasis_agent -- image --> yolov5/op
  oasis_agent -- lidar_pc --> obstacle_location_op/op
  yolov5/op -- bbox as obstacles_bbox --> obstacle_location_op/op
  oasis_agent -- position --> obstacle_location_op/op
  carla_gps_op/op -- gps_waypoints --> fot_op/op
  obstacle_location_op/op -- obstacles --> fot_op/op
  oasis_agent -- position --> fot_op/op
  oasis_agent -- speed --> fot_op/op
  oasis_agent -- position --> pid_control_op/op
  oasis_agent -- speed --> pid_control_op/op
  fot_op/op -- waypoints --> pid_control_op/op
```

To test it out:

```bash
./scripts/launch.sh -b -s -g tutorials/carla_full.yaml
```

- To run it without docker:

```bash
dora-daemon --run-dataflow graphs/tutorials/carla_full.yaml
```

😎 We now have a working autonomous car!