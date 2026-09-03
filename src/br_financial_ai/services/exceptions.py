class CompanyAlreadyExistsError(Exception):
    pass


class SecurityAlreadyExistsError(Exception):
    pass


class CvmCompanyNotFoundError(Exception):
    pass


class CompanyNotFoundError(Exception):
    pass


class MetricUnsupportedForProfileError(ValueError):
    def __init__(
        self,
        metric_key: str,
        financial_profile: str,
    ) -> None:
        self.metric_key = metric_key
        self.financial_profile = financial_profile
        super().__init__(
            f"Financial metric {metric_key} is unsupported for "
            f"profile {financial_profile}."
        )


class NewsClassificationError(Exception):
    pass


class RecommendationGenerationError(Exception):
    pass


class PreferredSecurityMismatchError(Exception):
    pass


class InvalidTickerError(Exception):
    pass


class TickerNotFoundError(Exception):
    pass


class OnboardingJobNotFoundError(Exception):
    pass


class OnboardingNotRetryableError(Exception):
    pass
