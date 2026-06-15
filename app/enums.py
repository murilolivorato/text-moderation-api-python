"""
Status / level enums used by the text-moderation flow. The string values are
the ones written into the moderation log returned by the API.
"""

from enum import Enum


class GnlSentimentStatus(str, Enum):
    POSITIVE = "positive-sentiment"
    NEUTRAL = "neutral-sentiment"
    NEGATIVE = "negative-sentiment"


class GnlSyntaxLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GnlSyntaxStatus(str, Enum):
    SYNTACTICALLY_CORRECT = "Text appears to be syntactically correct"
    UNEXPECTED_API_RESPONSE_ERROR = "Unexpected API response error"
    TEXT_TOO_SHORT_OR_EMPTY = "Text is too short or empty"
    STRUCTURAL_ISSUES = "Text may have structural issues (very short or very long sentences)"
    LACK_VERBS = "Text seems to lack verbs, indicating a syntactic issue"
    LACK_NOUNS_CLEAR_SENTENCES = "Text may lack enough nouns to form clear sentences"
    LACK_NOUNS_PROPER_STRUCTURE = "Text seems to lack enough nouns for proper syntactic structure"
    TOO_MANY_VERBS = "Text seems to have too many verbs, indicating disjointed sentences"
    LACK_ADJECTIVES = "Text may lack enough adjectives, making the description vague"
    TOO_MANY_PRONOUNS = "Text uses too many pronouns, making it hard to understand"


class GnlModerateStatus(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
