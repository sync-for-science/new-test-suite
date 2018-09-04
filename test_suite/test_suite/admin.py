from django.contrib import admin

from test_suite.models import SuiteRun, FeatureRun, Scenario, Resource


class FeatureRunInline(admin.StackedInline):
    model = FeatureRun


class SuiteRunAdmin(admin.ModelAdmin):
    inlines = [FeatureRunInline]


class ScenarioInline(admin.StackedInline):
    model = Scenario


class FeatureRunAdmin(admin.ModelAdmin):
    inlines = [ScenarioInline]


admin.site.register(SuiteRun, SuiteRunAdmin)
admin.site.register(FeatureRun, FeatureRunAdmin)
admin.site.register(Scenario)
admin.site.register(Resource)
