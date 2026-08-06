from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (RoleMasterViewSet,UserMasterViewSet,DomainMasterViewSet,
                    CandidateStatusMasterViewSet,ApplicationStatusMasterViewSet,PositionStatusMasterViewSet,
                    SkillMasterViewSet,
                    ClientManagerMasterViewSet,ClientMasterViewSet,ReqStatusMasterViewSet,
                    PriorityMasterViewSet,NoticePeriodMasterViewSet,
                    ReqTypeMasterViewSet,WorkModeMasterViewSet,SourceMasterViewSet,
                    ScreeningModeMasterViewSet,RejectionReasonMasterViewSet,
                    EmailTemplateMasterViewSet,
                    LocationMasterViewSet,DashboardAPIView
                    )
from .views import ProfileView

router = DefaultRouter()
router.register(r'roles', RoleMasterViewSet)
router.register(r'users', UserMasterViewSet)
router.register(r'domains', DomainMasterViewSet)
router.register(r'candidate-status', CandidateStatusMasterViewSet)
router.register(r'application-status', ApplicationStatusMasterViewSet)
router.register(r'position-status', PositionStatusMasterViewSet)
router.register(r"skills", SkillMasterViewSet)
router.register(r'clients', ClientMasterViewSet)
router.register(r'client-managers', ClientManagerMasterViewSet)
router.register(r'req-status', ReqStatusMasterViewSet)
router.register(r'priorities', PriorityMasterViewSet)
router.register(r'notice-periods', NoticePeriodMasterViewSet)
router.register(r'req-types', ReqTypeMasterViewSet)
router.register(r'work-modes', WorkModeMasterViewSet)
router.register(r'sources', SourceMasterViewSet)
router.register(r'screening-modes', ScreeningModeMasterViewSet)
router.register(r'rejection-reasons', RejectionReasonMasterViewSet)
router.register(r'email-templates', EmailTemplateMasterViewSet)
router.register(r'locations', LocationMasterViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("profile/", ProfileView.as_view(), name="profile"),
]