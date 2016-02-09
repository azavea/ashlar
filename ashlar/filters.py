import json
import django_filters

from django.contrib.gis.geos import GEOSGeometry
from dateutil.parser import parse

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from rest_framework.exceptions import ParseError, NotFound
from rest_framework.filters import BaseFilterBackend
from rest_framework_gis.filterset import GeoFilterSet

from ashlar.models import Boundary, BoundaryPolygon, Record, RecordType
from ashlar.exceptions import QueryParameterException


class RecordFilter(GeoFilterSet):

    record_type = django_filters.MethodFilter(name='record_type', action='filter_record_type')
    polygon = django_filters.MethodFilter(name='polygon', action='filter_polygon')
    polygon_id = django_filters.MethodFilter(name='polygon_id', action='filter_polygon_id')

    def filter_polygon(self, queryset, geojson):
        """ Method filter for arbitrary polygon, sent in as geojson.
        """
        poly = GEOSGeometry(geojson)
        if poly.valid:
            return queryset.filter(geom__intersects=poly)
        else:
            raise ParseError('Input polygon must be valid GeoJSON: ' + poly.valid_reason)

    def filter_polygon_id(self, queryset, poly_uuid):
        """ Method filter for containment within the polygon specified by poly_uuid"""
        if not poly_uuid:
            return queryset
        try:
            return queryset.filter(geom__intersects=BoundaryPolygon.objects.get(pk=poly_uuid).geom)
        except ValueError as e:
            raise ParseError(e)
        except BoundaryPolygon.DoesNotExist as e:
            raise NotFound(e)
        # It would be preferable to do something like this to avoid loading the whole geometry into
        # Python, but this currently raises 'Complex expressions not supported for GeometryField'
        #return queryset.filter(geom__intersects=RawSQL(
        #    'SELECT geom FROM ashlar_boundarypolygon WHERE uuid=%s', (poly_uuid,)
        #))

    def filter_record_type(self, queryset, value):
        """ Method filter for records having a desired record type (uuid)

        e.g. /api/records/?record_type=44a51b83-470f-4e3d-b71b-e3770ec79772

        """
        return queryset.filter(schema__record_type=value)

    class Meta:
        model = Record
        fields = ['data', 'record_type', 'geom', 'archived']


class RecordTypeFilter(django_filters.FilterSet):

    class Meta:
        model = RecordType
        fields = ['active', 'label']


class BoundaryFilter(GeoFilterSet):

    STATUS_SET = {status[0] for status in Boundary.StatusTypes.CHOICES}

    status = django_filters.MethodFilter(name='status', action='multi_filter_status')

    def multi_filter_status(self, queryset, value):
        """ Method filter for multiple choice query on status

        e.g. /api/boundary/?status=ERROR,WARNING

        """
        statuses = value.split(',')
        statuses = set(statuses) & self.STATUS_SET
        return queryset.filter(status__in=statuses)

    class Meta:
        model = Boundary
        fields = ['status']


class BoundaryPolygonFilter(GeoFilterSet):

    boundary = django_filters.MethodFilter(name='boundary', action='filter_boundary')

    def filter_boundary(self, queryset, value):
        """ Method filter for boundary polygons having a desired boundary (uuid)

        e.g. /api/boundarypolygons/?boundary=44a51b83-470f-4e3d-b71b-e3770ec79772

        """
        return queryset.filter(boundary=value)

    class Meta:
        model = BoundaryPolygon
        fields = ['data', 'boundary']


class DateRangeFilterBackend(BaseFilterBackend):
    """Used to filter querysets based on a given START_FIELD and END_FIELD

    NOTE: This filter must be inherited from in order to be used because
    1. its Meta class must be set with a model and list of fields
    2. you likely want to override START_FIELD/END_FIELD

    This is a simple filter which takes two (optional) limits and returns all records
    whose 'occurred_from' field falls on or between the maximum and minimum provided.
    If only a maximum or a minimum are provided, the MIN_DATETIME or MAX_DATETIME will
    be used instead.

    An example [truncated] query: /api/records/?occurred_min=1901-01-01T00:00:00+00:00Z
    """

    MIN_DATETIME = '1901-01-01T00:00:00+00:00'
    MAX_DATETIME = '9999-12-31T23:59:59.999999+00:00'

    FIELD = 'occurred_from'

    def filter_queryset(self, request, queryset, view):
        """Filter records by date

        Arguments
        :param request: django rest framework request instance
        :param queryset: queryset to apply filter to
        :param view: view that this filter is being used by

        QUERY PARAMS
        :param valid_from: ISO 8601 timestamp
        :param valid_to: ISO 8601 timestamp
        """
        occurred_min = 'occurred_min'
        occurred_max = 'occurred_max'
        err_msg = 'must be ISO 8601 formatted with timezone information. Please check that the URL is properly encoded.'
        if occurred_min not in request.query_params and occurred_max not in request.query_params:
            return queryset

        try:
            min_date = parse(request.query_params.get(occurred_min, self.MIN_DATETIME))
        except:
            raise QueryParameterException(occurred_min, err_msg)

        try:
            max_date = parse(request.query_params.get(occurred_max, self.MAX_DATETIME))
        except:
            raise QueryParameterException(occurred_max, err_msg)

        if not min_date.tzinfo or not max_date.tzinfo:
            raise QueryParameterException('datetimes', err_msg)

        return queryset.filter(occurred_from__gte=min_date, occurred_from__lte=max_date)


class JsonBFilterBackend(BaseFilterBackend):
    """ Generic configurable filter for JsonBField

    Requires the following properties, configured on the view using this filter backend:

    jsonb_filter_field: The name of the django model field to filter against
    NOTE: Currently, there can be at most one jsonb field to filter over. parametrizing
    the fieldnames will allow indefinitely many filtered columns.

    EXAMPLE USAGE: /api/records/?jcontains={"Site": {"DPWH province name": "CAGAYAN"}}
    """
    def filter_queryset(self, request, queryset, view):
        """ Filter by configured jsonb_filters on jsonb_filter_field """
        lookup_name = 'jsonb'
        filter_field = getattr(view, 'jsonb_filter_field', None)
        if not filter_field:
            raise ImproperlyConfigured('JsonBFilterBackend requires property ' +
                                       '`jsonb_filter_field` on view')

        filter_value = request.query_params.get(lookup_name, None)

        if not filter_value:
            return queryset

        filter_key = '{0}__{1}'.format(filter_field, lookup_name)
        try:
            json_data = json.loads(filter_value)
        except ValueError as e:
            raise ParseError(str(e))

        if isinstance(json_data, dict):
            queryset = queryset.filter(Q(**{filter_key: json_data}))
        else:
            raise ParseError('Lookup must be an object')

        return queryset
