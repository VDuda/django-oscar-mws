from django.contrib import admin
from django.conf import settings
from django.conf.urls import patterns, include, url

from oscar.app import shop
from oscar_mws.dashboard.app import application as mws_app


admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^dashboard/', include(mws_app.urls)),
    url(r'', include(shop.urls)),
)

if settings.DEBUG:
    urlpatterns += patterns(
        '',
        url(
            r'^media/(?P<path>.*)$',
            'django.views.static.serve', {
                'document_root': settings.MEDIA_ROOT,
            }
        ),
    )
