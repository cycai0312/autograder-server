from rest_framework import serializers
from django.core import exceptions


class AGModelSerializer(serializers.BaseSerializer):
    """
    The purpose of this base class is to push data validation down to
    the database level while making it still be possible to use django-
    rest-framework's generic views when desired.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.include_fields = None
        self.exclude_fields = None

        if not self.context:
            return

        request_params = self.context['request'].query_params
        if 'include_fields' in request_params:
            self.include_fields = request_params.getlist('include_fields')
        if 'exclude_fields' in request_params:
            self.exclude_fields = request_params.getlist('exclude_fields')

    def get_ag_model_manager(self):
        """
        Returns a django model manager object that can be used to create
        objects of the desired autograder model type.

        Derived classes should either override this method or override
        validate_and_create with an implementation that doesn't call
        this method.
        """
        raise NotImplementedError(
            "Derived classes should override either this method or"
            "validate_and_create")

    def to_representation(self, obj):
        return obj.to_dict(include_fields=self.include_fields,
                           exclude_fields=self.exclude_fields)

    # Derived classes may need to override this if any sub-objects need
    # to be deserialized (for example, FeedbackConfig objects)
    def to_internal_value(self, data):
        return data

    def create(self, validated_data):
        try:
            return self.validate_and_create(validated_data)
        except exceptions.ValidationError as e:
            raise serializers.ValidationError(e.message_dict)

    def validate_and_create(self, data):
        return self.get_ag_model_manager().validate_and_create(**data)

    def update(self, instance, validated_data):
        try:
            instance.validate_and_update(**validated_data)
            return instance
        except exceptions.ValidationError as e:
            raise serializers.ValidationError(e.message_dict)

    # Since we're pushing the validation down to the database
    # level, this method should return the given data unmodified.
    def run_validation(self, initial_data):
        return initial_data