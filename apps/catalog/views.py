from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from apps.core.permissions import ReadOnlyOrAdmin

from .models import Curriculum, Grade, Stage, Subject
from .serializers import CurriculumSerializer, GradeSerializer, StageSerializer, SubjectSerializer


class _PublicMixin:
    permission_classes = [ReadOnlyOrAdmin]

    def get_authenticators(self):
        return super().get_authenticators()


@extend_schema_view(list=extend_schema(summary="المناهج مع المراحل والصفوف (شجرة كاملة)"))
@extend_schema(tags=["Catalog"])
class CurriculumViewSet(_PublicMixin, viewsets.ModelViewSet):
    serializer_class = CurriculumSerializer
    pagination_class = None
    queryset = Curriculum.objects.filter(is_active=True).prefetch_related("stages__grades")
    lookup_field = "slug"


@extend_schema(tags=["Catalog"])
class StageViewSet(_PublicMixin, viewsets.ModelViewSet):
    serializer_class = StageSerializer
    pagination_class = None
    queryset = Stage.objects.prefetch_related("grades")
    filterset_fields = ["curriculum"]


@extend_schema(tags=["Catalog"])
class GradeViewSet(_PublicMixin, viewsets.ModelViewSet):
    serializer_class = GradeSerializer
    pagination_class = None
    queryset = Grade.objects.select_related("stage")
    filterset_fields = ["stage", "stage__curriculum"]


@extend_schema_view(
    list=extend_schema(summary="المواد (فلترة بالصف ?grades=ID، المميزة ?is_featured=true، بحث ?search=)"),
)
@extend_schema(tags=["Catalog"])
class SubjectViewSet(_PublicMixin, viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    pagination_class = None
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"
    filterset_fields = ["grades", "is_featured"]
    search_fields = ["name", "name_en"]

    def get_queryset(self):
        qs = Subject.objects.all() if getattr(self.request.user, "role", None) == "admin" else Subject.objects.filter(is_active=True)
        return qs.annotate(
            teachers_count=Count("teachers", filter=Q(teachers__approval_status="approved"), distinct=True),
            courses_count=Count("courses", filter=Q(courses__status="published"), distinct=True),
        ).distinct()
