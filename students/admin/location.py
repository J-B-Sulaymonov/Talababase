from .base import *

# (O'zgarishsiz qoldirildi)
# =============================================================================
class CountryResource(resources.ModelResource):
    class Meta:
        model = Country


@admin.register(Country)
class CountryAdmin(ImportExportModelAdmin):
    resource_class = CountryResource
    list_display = ('name', 'id')
    search_fields = ('name',)


class RegionResource(resources.ModelResource):
    class Meta:
        model = Region


@admin.register(Region)
class RegionAdmin(ImportExportModelAdmin):
    resource_class = RegionResource
    list_display = ('name', 'country', 'id')
    list_filter = ('country',)
    search_fields = ('name',)
    autocomplete_fields = ['country']


class DistrictResource(resources.ModelResource):
    class Meta:
        model = District


@admin.register(District)
class DistrictAdmin(ImportExportModelAdmin):
    resource_class = DistrictResource
    list_display = ('name', 'region', 'id')
    list_filter = ('region__country', 'region')
    search_fields = ('name',)
    autocomplete_fields = ['region']


