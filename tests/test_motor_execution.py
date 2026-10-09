from polcomp.motor_execution import MotorExecutor
from polcomp.polcomp import (
    CompensationState,
    SearchState,
)
from polcomp.jacobian_search import (
    JacobianAction,
    JacobianActionType,
)


class RecordingMotor:
    def __init__(
        self,
        position=0.0,
        is_moving=False,
    ):
        self.position = position
        self.is_moving = is_moving
        self.commands = []

    def stop(self):
        self.commands.append(('stop',))
        self.is_moving = False

    def move_to(self, position):
        self.commands.append(('move_to', position))
        self.position = position

    def jog(self, *, direction, max_velocity):
        self.commands.append(
            ('jog', direction, max_velocity)
        )
        self.is_moving = True


def test_stop_moving():
    moving = RecordingMotor(is_moving=True)
    stationary = RecordingMotor(is_moving=False)

    executor = MotorExecutor([moving, stationary])

    executor.stop_moving()

    assert moving.commands == [('stop',)]
    assert stationary.commands == []

def test_stop_and_move_to():
    waveplate = RecordingMotor(
        position=10.0,
        is_moving=True,
    )

    executor = MotorExecutor([waveplate])

    executor.stop_and_move_to(
        index=0,
        position=25.0,
    )

    assert waveplate.commands == [
        ('stop',),
        ('move_to', 25.0),
    ]

def test_apply_step():
    motors = [
        RecordingMotor(position=10.0),
        RecordingMotor(position=20.0),
        RecordingMotor(position=30.0),
    ]

    executor = MotorExecutor(motors)

    executor.apply_step(
        (5.0, -10.0, 15.0)
    )

    assert motors[0].commands == [
        ('move_to', 15.0),
    ]

    assert motors[1].commands == [
        ('move_to', 10.0),
    ]

    assert motors[2].commands == [
        ('move_to', 45.0),
    ]

def test_is_moving():
    motors = [
        RecordingMotor(is_moving=False),
        RecordingMotor(is_moving=True),
    ]

    executor = MotorExecutor(motors)

    assert executor.is_moving

    motors[1].is_moving = False

    assert not executor.is_moving

def test_jog():
    waveplate = RecordingMotor()

    executor = MotorExecutor([waveplate])

    executor.jog(
        index=0,
        direction='positive',
        max_velocity=5.0,
    )

    assert waveplate.commands == [
        ('jog', 'positive', 5.0),
    ]

def test_controller_stop_uses_executor(controller):
    controller.qwp1.is_moving = True
    controller.hwp.is_moving = False
    controller.qwp2.is_moving = True

    controller.stop()

    controller.qwp1.stop.assert_called_once_with()
    controller.hwp.stop.assert_not_called()
    controller.qwp2.stop.assert_called_once_with()

    assert not controller.active
    assert controller.state is CompensationState.IDLE

def test_controller_executes_jacobian_move(controller):
    action = JacobianAction(
        type=JacobianActionType.MOVE_TO,
        motor_index=1,
        position=45.0,
    )

    controller._execute_jacobian_action(action)

    controller.hwp.move_to.assert_called_once_with(45.0)

    controller.qwp1.move_to.assert_not_called()
    controller.qwp2.move_to.assert_not_called()

def test_controller_executes_jacobian_step(controller):
    controller.qwp1.position = 10.0
    controller.hwp.position = 20.0
    controller.qwp2.position = 30.0

    initial_iteration = (
        controller._jacobian_search.state.iteration
    )

    action = JacobianAction(
        type=JacobianActionType.APPLY_STEP,
        step=(5.0, -10.0, 15.0),
    )

    controller._execute_jacobian_action(action)

    controller.qwp1.move_to.assert_called_once_with(15.0)
    controller.hwp.move_to.assert_called_once_with(10.0)
    controller.qwp2.move_to.assert_called_once_with(45.0)

    assert (
        controller._jacobian_search.state.iteration
        == initial_iteration + 1
    )

    assert (
        controller._search_state
        is SearchState.JACOBIAN_APPLY
    )

def test_position():
    motors = [
        RecordingMotor(position=10.0),
        RecordingMotor(position=20.0),
        RecordingMotor(position=30.0),
    ]

    executor = MotorExecutor(motors)

    assert executor.position(1) == 20.0

    motors[1].position = 25.0

    assert executor.position(1) == 25.0


def test_positions():
    motors = [
        RecordingMotor(position=10.0),
        RecordingMotor(position=20.0),
        RecordingMotor(position=30.0),
    ]

    executor = MotorExecutor(motors)

    assert executor.positions() == (
        10.0,
        20.0,
        30.0,
    )