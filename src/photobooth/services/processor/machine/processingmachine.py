from statemachine import Event, State, StateMachine

# TODO: can use as enum so fastapi can use this type also and validate states?
# class Status(Enum):
#     start = auto()
#     counting = auto()
#     capture = auto()
#     approval = auto()
#     completed = auto()
#     finished = auto()


class ProcessingMachine(StateMachine):
    """ """

    ## STATES

    # _ = States.from_enum(Status, initial=Status.start, final=Status.finished)

    start = State(initial=True)
    counting = State()  # countdown before capture
    capture = State()  # capture from camera include postprocess single img postproc
    approval = State()  # waiting state to approve. transition by confirm,reject or autoconfirm
    completed = State()  # final postproc (mostly to create collage/gif)
    present = State()  # present state
    finished = State(final=True)

    ## TRANSITIONS

    next = Event(
        # first next is from start (init state) to counting
        start.to(counting)
        # second next is always to capture
        | counting.to(capture)
        # now check if need to approve something, then go to approval state
        | capture.to(approval, cond="sm_cond_ask_user_for_approval")
        ## START: two paths here: either all captures done or no
        | counting.from_(approval, capture, unless="sm_cond_all_captures_done")  # return to countdown to get the remaining captures
        | completed.from_(approval, capture, cond="sm_cond_all_captures_done")  # to completed, only if all captures 100% sure done
        ## END: two paths
        # after completed have dedicated present state to prevent any race conditions in frontend that cannot distinguish between idle and present.
        | completed.to(present)
        # after completed, all phase2 procs are done, so the UI can rely on source=completed target=finished to present something
        | present.to(finished)
    )
    reject = Event(approval.to(counting))
    abort = Event(finished.from_(start, counting, capture, approval, completed, present))

    # loop = Event(counting.to.itself())
