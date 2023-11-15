
class ParseError(RuntimeError):
    pass


class CheckError(ParseError):
    pass


class ActionError(ParseError):
    pass


class NoArgLeftError(ParseError):
    pass


class TooFewArgsError(ParseError):
    pass
