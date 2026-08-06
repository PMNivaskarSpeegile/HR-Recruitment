from rest_framework.routers import DefaultRouter

from .views import CandidateViewSet, DuplicateReviewViewSet, ImportBatchViewSet

router = DefaultRouter()
router.register(r"candidates", CandidateViewSet, basename="candidate")
router.register(r"duplicate-reviews", DuplicateReviewViewSet, basename="duplicate-review")
router.register(r"import-batches", ImportBatchViewSet, basename="import-batch")

urlpatterns = router.urls
