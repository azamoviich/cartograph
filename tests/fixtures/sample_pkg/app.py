import os
from .helpers import helper_fn
from .sub.deep import DeepThing


class App:
    def run(self) -> None:
        helper_fn()
        DeepThing()
