from django.urls import path

from .views import (
    AdvanceView,
    CommunicationListView,
    JdPreviewView,
    MappingListView,
    MappingTimelineView,
    NewCvListView,
    OutcomeView,
    RescheduleView,
    ReviewView,
    ScreeningCompleteView,
    ScreeningRescheduleView,
    ScreeningListCreateView,
    SendJdView,
    TransitionView,
)

urlpatterns = [
    path("pipeline/new-cvs/", NewCvListView.as_view(), name="pipeline-new-cvs"),
    path("pipeline/review/", ReviewView.as_view(), name="pipeline-review"),
    path("pipeline/mappings/", MappingListView.as_view(), name="pipeline-mappings"),
    path("pipeline/mappings/<int:pk>/timeline/", MappingTimelineView.as_view(), name="pipeline-mapping-timeline"),
    path("pipeline/jd-preview/", JdPreviewView.as_view(), name="pipeline-jd-preview"),
    path("pipeline/send-jd/", SendJdView.as_view(), name="pipeline-send-jd"),
    path("pipeline/communications/", CommunicationListView.as_view(), name="pipeline-communications"),
    # Centralized Stage × Outcome engine endpoints.
    path("pipeline/outcome/", OutcomeView.as_view(), name="pipeline-outcome"),
    path("pipeline/advance/", AdvanceView.as_view(), name="pipeline-advance"),
    path("pipeline/reschedule/", RescheduleView.as_view(), name="pipeline-reschedule"),
    path("pipeline/transition/", TransitionView.as_view(), name="pipeline-transition"),  # back-compat
    path("pipeline/screenings/", ScreeningListCreateView.as_view(), name="pipeline-screenings"),
    path("pipeline/screenings/<int:pk>/complete/", ScreeningCompleteView.as_view(), name="pipeline-screening-complete"),
    path("pipeline/screenings/<int:pk>/reschedule/", ScreeningRescheduleView.as_view(), name="pipeline-screening-reschedule"),
]
