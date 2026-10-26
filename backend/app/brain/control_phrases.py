"""Bounded conversation controls; courtesy is never authorization to write."""
import re

from app.schemas import Intent


AFFIRMATIVE = r"(?:yes|yeah|yep|sure|okay|ok)"
COURTESY = r"(?:thanks(?: (?:a lot|so much))?|thank you(?: (?:so|very) much)?|cheers)"
POLITE = rf"(?:please|{COURTESY})"
DISCARD_TARGET = r"(?:(?:this|that|the|my|pending|proposed) )?(?:change|reschedule|rescheduling|draft|proposal|new booking|new appointment)"
DISCARD = rf"(?:cancel|discard|undo|forget|revert|drop|scrap) {DISCARD_TARGET}"
NEGATED_EXECUTION = (
    r"(?:do not|don't) (?:do (?:it|that)"
    r"|apply (?:(?:this|that|the) )?(?:change|proposal|reschedule)"
    r"|confirm (?:(?:this|that|the) )?(?:change|proposal|booking|appointment)"
    r"|book|cancel)"
)
KEEP_ORIGINAL = r"keep (?:(?:my|the|this|that) )?(?:original|current|existing) (?:appointment|booking|time)"
DENIAL_CLAUSE = rf"(?:please )?(?:no|nope|not yet|do not|don't|never mind|nevermind|forget it|{NEGATED_EXECUTION}|{DISCARD}|{KEEP_ORIGINAL})"
END = (
    r"(?:goodbye|bye|end (?:the )?(?:call|conversation)|stop|hang up"
    r"|nothing(?: else)?|no more|that's all|that is all|that's it|that is it"
    r"|i'm done|i am done|we're done|we are done|all done)"
)


def recognize_control(text: str) -> tuple[Intent, str] | None:
    """Match entire normalized utterances, including repeated denial clauses."""
    rules = [
        (Intent.END, "control.end", rf"(?:{COURTESY} )?{END}(?: {POLITE})?"),
        (Intent.DENY, "context.discard_proposal", rf"(?:please )?{DISCARD}(?: {POLITE})?"),
        (Intent.REPEAT, "control.repeat", r"(?:repeat(?: that)?|say that again|pardon|what did you say)"),
        (Intent.DENY, "confirmation.deny", rf"{DENIAL_CLAUSE}(?: (?:and )?{DENIAL_CLAUSE})*(?: {POLITE})?"),
        (Intent.CONFIRM, "confirmation.explicit", rf"(?:{AFFIRMATIVE}(?: please)?(?: (?:do it|go ahead))?|sounds good|confirm(?: it| booking| cancellation| reschedule)?|(?:please )?do it|go ahead|that's correct|that is correct|correct|please confirm)"),
        (Intent.INFO, "control.thanks", COURTESY),
    ]
    for intent, rule, pattern in rules:
        if re.fullmatch(pattern, text):
            return intent, rule
    return None
