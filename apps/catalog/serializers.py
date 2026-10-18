from rest_framework import serializers

from .models import Curriculum, Grade, Stage, Subject


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ["id", "name", "order", "stage"]


class StageSerializer(serializers.ModelSerializer):
    grades = GradeSerializer(many=True, read_only=True)

    class Meta:
        model = Stage
        fields = ["id", "name", "order", "curriculum", "grades"]


class CurriculumSerializer(serializers.ModelSerializer):
    stages = StageSerializer(many=True, read_only=True)

    class Meta:
        model = Curriculum
        fields = ["id", "name", "slug", "country", "order", "is_active", "stages"]
        read_only_fields = ["slug"]


class SubjectSerializer(serializers.ModelSerializer):
    teachers_count = serializers.IntegerField(read_only=True, required=False)
    courses_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Subject
        fields = [
            "id", "name", "name_en", "slug", "icon", "color", "description", "grades",
            "is_active", "is_featured", "order", "meta_title", "meta_description",
            "teachers_count", "courses_count",
        ]
        read_only_fields = ["slug"]


class SubjectMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "slug", "icon", "color"]
