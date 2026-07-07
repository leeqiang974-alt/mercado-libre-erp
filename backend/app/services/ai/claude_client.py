from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.review_policy import review_draft_locally


class ClaudeReviewClient:
    def review_draft(self, draft: ProductDraftCreate) -> ReviewResponse:
        result = review_draft_locally(draft)
        return result.model_copy(update={"provider": "claude_stub"})
