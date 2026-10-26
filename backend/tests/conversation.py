"""Drive a whole call through NLU + DialogueManager, the way the API will."""

from datetime import datetime

from app.db.repository import ClinicRepository
from app.dialogue.frame import Frame
from app.dialogue.manager import Decision, DialogueManager
from app.nlu.pipeline import parse


class Call:
    def __init__(self, session, classifier, now: datetime):
        self.now = now
        self.classifier = classifier
        self.repo = ClinicRepository(session, now=lambda: self.now)
        self.manager = DialogueManager(self.repo, seed=0)
        self.frame = Frame()
        self.decisions: list[Decision] = [self.manager.start(self.frame)]

    @property
    def last(self) -> Decision:
        return self.decisions[-1]

    def say(self, text: str) -> Decision:
        nlu = parse(
            text, expected_slot=self.frame.expected_slot, now=self.now, classifier=self.classifier
        )
        decision = self.manager.handle(nlu, self.frame)
        self.decisions.append(decision)
        return decision

    def transcript(self) -> str:
        return "\n".join(f"agent: {d.reply_text}" for d in self.decisions)
