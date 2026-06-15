"""
Service wrapper around the Google Cloud Natural Language API.

It exposes a three-step text-moderation evaluation flow:
  - analyzeSentiment  -> evaluate_sentiment()  (status / score / magnitude)
  - analyzeSyntax     -> evaluate_syntax()     (level / status)
  - moderateText      -> evaluate_moderation() (status / score / categories)

It uses the official google-cloud-language client, which reads the service
account from GOOGLE_APPLICATION_CREDENTIALS automatically.
"""

from google.cloud import language_v1, language_v2

from enums import (
    GnlModerateStatus,
    GnlSentimentStatus,
    GnlSyntaxLevel,
    GnlSyntaxStatus,
)


class GoogleNaturalLanguage:
    LANGUAGE = "pt-BR"

    def __init__(self):
        self._v1 = language_v1.LanguageServiceClient()
        self._v2 = language_v2.LanguageServiceClient()

    # -- raw API calls -------------------------------------------------------

    def _document_v1(self, text: str) -> language_v1.Document:
        return language_v1.Document(
            content=text,
            type_=language_v1.Document.Type.PLAIN_TEXT,
            language=self.LANGUAGE,
        )

    def analyze_sentiment(self, text: str):
        return self._v1.analyze_sentiment(
            request={
                "document": self._document_v1(text),
                "encoding_type": language_v1.EncodingType.UTF8,
            }
        )

    def analyze_syntax(self, text: str):
        return self._v1.analyze_syntax(
            request={
                "document": self._document_v1(text),
                "encoding_type": language_v1.EncodingType.UTF8,
            }
        )

    def moderate_text(self, text: str):
        document = language_v2.Document(
            content=text,
            type_=language_v2.Document.Type.PLAIN_TEXT,
        )
        return self._v2.moderate_text(request={"document": document})

    # -- evaluations ---------------------------------------------------------

    def evaluate_sentiment(self, text: str) -> dict:
        response = self.analyze_sentiment(text)
        sentiment = response.document_sentiment
        sentences = response.sentences

        if not sentences:
            return {
                "status": GnlSentimentStatus.NEUTRAL.value,
                "score": round(sentiment.score, 4),
                "magnitude": round(sentiment.magnitude, 4),
            }

        total = sum(s.sentiment.score for s in sentences)
        average = total / len(sentences)

        if average > 0.1:
            status = GnlSentimentStatus.POSITIVE
        elif average < -0.1:
            status = GnlSentimentStatus.NEGATIVE
        else:
            status = GnlSentimentStatus.NEUTRAL

        return {
            "status": status.value,
            "score": round(sentiment.score, 4),
            "magnitude": round(sentiment.magnitude, 4),
        }

    def evaluate_syntax(self, text: str) -> dict:
        response = self.analyze_syntax(text)
        sentences = response.sentences
        tokens = response.tokens

        if not sentences or not tokens:
            return {
                "level": GnlSyntaxLevel.HIGH.value,
                "status": GnlSyntaxStatus.TEXT_TOO_SHORT_OR_EMPTY.value,
            }

        sentence_count = len(sentences)
        token_count = len(tokens)
        average_sentence_length = token_count / sentence_count

        if average_sentence_length < 3 or average_sentence_length > 30:
            return {
                "level": GnlSyntaxLevel.MEDIUM.value,
                "status": GnlSyntaxStatus.STRUCTURAL_ISSUES.value,
            }

        counts = {"NOUN": 0, "VERB": 0, "ADJ": 0, "ADV": 0, "PRON": 0}
        for token in tokens:
            tag = language_v1.PartOfSpeech.Tag(token.part_of_speech.tag).name
            if tag in counts:
                counts[tag] += 1

        if counts["VERB"] == 0:
            return {
                "level": GnlSyntaxLevel.HIGH.value,
                "status": GnlSyntaxStatus.LACK_VERBS.value,
            }

        if counts["NOUN"] < 2:
            return {
                "level": GnlSyntaxLevel.MEDIUM.value,
                "status": GnlSyntaxStatus.LACK_NOUNS_CLEAR_SENTENCES.value,
            }

        if counts["NOUN"] / token_count < 0.2:
            return {
                "level": GnlSyntaxLevel.HIGH.value,
                "status": GnlSyntaxStatus.LACK_NOUNS_PROPER_STRUCTURE.value,
            }

        verb_ratio = counts["VERB"] / token_count
        adj_ratio = counts["ADJ"] / token_count
        pron_ratio = counts["PRON"] / token_count

        if verb_ratio > 0.4:
            return {
                "level": GnlSyntaxLevel.MEDIUM.value,
                "status": GnlSyntaxStatus.TOO_MANY_VERBS.value,
            }

        if adj_ratio < 0.05:
            return {
                "level": GnlSyntaxLevel.LOW.value,
                "status": GnlSyntaxStatus.LACK_ADJECTIVES.value,
            }

        if pron_ratio > 0.25:
            return {
                "level": GnlSyntaxLevel.MEDIUM.value,
                "status": GnlSyntaxStatus.TOO_MANY_PRONOUNS.value,
            }

        return {
            "level": GnlSyntaxLevel.LOW.value,
            "status": GnlSyntaxStatus.SYNTACTICALLY_CORRECT.value,
        }

    def evaluate_moderation(self, text: str) -> dict:
        response = self.moderate_text(text)
        categories = response.moderation_categories

        moderation_score = 0
        concerning = []
        total_confidence = 0.0
        category_count = 0

        for category in categories:
            category_count += 1
            if category.confidence > 0.05:
                moderation_score += 1
                concerning.append(category.name.lower())
                total_confidence += category.confidence

        average_confidence = total_confidence / category_count if category_count else 0.0

        if moderation_score <= 1 and average_confidence < 0.3:
            status = GnlModerateStatus.LOW
        elif moderation_score <= 3 and average_confidence < 0.6:
            status = GnlModerateStatus.MEDIUM
        else:
            status = GnlModerateStatus.HIGH

        return {
            "status": status.value,
            "score": moderation_score,
            "categories": concerning,
            "averageConfidence": round(average_confidence, 4),
        }
