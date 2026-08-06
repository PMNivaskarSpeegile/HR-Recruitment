from rest_framework.routers import DefaultRouter

from .views import RequirementViewSet

router = DefaultRouter()
router.register(r"requirements", RequirementViewSet, basename="requirement")

urlpatterns = router.urls
