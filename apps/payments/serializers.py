from rest_framework import serializers

from .models import Coupon, Order


class OrderSerializer(serializers.ModelSerializer):
    title = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = ["id", "reference", "kind", "title", "subscription", "course", "student", "amount", "discount", "total",
                  "currency", "status", "method", "paid_at", "created_at"]


class CheckoutSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Order.KINDS)
    subscription_id = serializers.IntegerField(required=False)
    course_id = serializers.IntegerField(required=False)
    coupon = serializers.CharField(required=False, allow_blank=True)

    def validate(self, a):
        if a["kind"] == "subscription" and not a.get("subscription_id"):
            raise serializers.ValidationError({"subscription_id": "مطلوب."})
        if a["kind"] == "course" and not a.get("course_id"):
            raise serializers.ValidationError({"course_id": "مطلوب."})
        return a


class CheckoutResponseSerializer(serializers.Serializer):
    order = OrderSerializer()
    checkout_url = serializers.CharField(allow_null=True)
    client_secret = serializers.CharField(allow_null=True)
    public_key = serializers.CharField(allow_null=True)
    success_url_prefix = serializers.CharField()


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()
    kind = serializers.ChoiceField(choices=Order.KINDS)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["id", "code", "percent_off", "amount_off", "applies_to", "max_uses", "used_count", "valid_from",
                  "valid_until", "is_active"]
        read_only_fields = ["used_count"]
