#pylint: disable=bare-except, invalid-name, too-many-nested-blocks, too-many-locals, too-many-branches
"""
    Utilities to communicate with ICAT server

    @author: M. Doucet, Oak Ridge National Laboratory
    @copyright: 2015 Oak Ridge National Laboratory
"""
import sys
import httplib
import xml.dom.minidom
import logging
from fitting.models import CatalogCache

try:
    from django.conf import settings
    ICAT_DOMAIN = settings.ICAT_DOMAIN
    ICAT_PORT = settings.ICAT_PORT
except:
    logging.warning("Could not find ICAT config: %s", sys.exc_value)
    ICAT_DOMAIN = 'icat.sns.gov'
    ICAT_PORT = 2080

def get_text_from_xml(nodelist):
    """
        Get text from an XML node list
        @param nodelist: nodes
    """
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

def get_run_info(instrument, run_number):
    """
        Get ICAT info for the specified run
    """
    run_info = {}
    cached_entry = CatalogCache.objects.filter(data_path="%s/%s" % (instrument, run_number))
    if len(cached_entry) > 0:
        return dict(title=cached_entry[0].title, proposal=cached_entry[0].proposal)

    # If we don't have the information, get it from ICAT
    try:
        conn = httplib.HTTPConnection(ICAT_DOMAIN,
                                      ICAT_PORT, timeout=3.0)
        url = '/icat-rest-ws/dataset/SNS/%s/%s/lite' % (instrument.upper(), run_number)
        conn.request('GET', url)
        r = conn.getresponse()
        dom = xml.dom.minidom.parseString(r.read())

        metadata = dom.getElementsByTagName('metadata')
        if len(metadata) > 0:
            for n in metadata[0].childNodes:
                # Run title
                if n.nodeName == 'title' and n.hasChildNodes():
                    run_info['title'] = get_text_from_xml(n.childNodes)
                if n.nodeName == 'proposal' and n.hasChildNodes():
                    run_info['proposal'] = get_text_from_xml(n.childNodes)
        if 'title' in run_info and 'proposal' in run_info:
            CatalogCache.objects.get_or_create(data_path="%s/%s" % (instrument, run_number),
                                               title=run_info['title'],
                                               proposal=run_info['proposal'])
    except:
        logging.error("Communication with ICAT server failed (%s): %s",url, sys.exc_value)

    return run_info
