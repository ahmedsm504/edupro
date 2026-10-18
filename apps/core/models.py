from django.db import models
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def unique_slug(instance, value, field="slug", max_length=200):
    """slug يدعم العربي ويضمن عدم التكرار."""
    base = slugify(value, allow_unicode=True)[:max_length] or "item"
    slug, i = base, 2
    Model = instance.__class__
    while Model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


def schema_safe(model):
    """ديكوريتور للـ ViewSets: وقت توليد الـ OpenAPI (المستخدم Anonymous) يرجّع queryset فاضي بدل ما يضرب."""
    def deco(cls):
        original = cls.get_queryset

        def get_queryset(self):
            if getattr(self, "swagger_fake_view", False):
                return model.objects.none()
            return original(self)

        cls.get_queryset = get_queryset
        return cls
    return deco
