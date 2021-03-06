import os
from django.core.management.base import BaseCommand, CommandError
from seak.models import ConservationFeature, PlanningUnit, Cost, PuVsCf, PuVsCost, DefinedGeography
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource
from django.template.defaultfilters import slugify
from seak.jenks import get_jenks_breaks
import json

def find_possible(key, possible):
    """
    Given a key and a list, find possible matches 
    Right now it just checks for case
    """
    if key in possible:
        return key
    possible = [x for x in possible if x.lower() == key]
    if possible == []:
        return None
    return possible[0]

class Command(BaseCommand):
    help = 'Imports shapefile with conservationfeatures/costs and xls metadata to planning units'
    args = '<shp_path> <xls_path> <optional: full resolution shp_path>'

    def handle(self, *args, **options):
        from django.conf import settings

        try: 
            shp = args[0]
            xls = args[1]
            assert os.path.exists(shp)
            assert os.path.exists(xls)
        except (AssertionError, IndexError):
            raise CommandError("Specify shp and xls file\n \
                    python manage.py import_planning_units test.shp test.xls <optional: full res shp>")

        try:
            fullres_shp = args[2]
            assert os.path.exists(fullres_shp)
        except (AssertionError, IndexError):
            print
            print "Using %s as the full-res display layer" % shp
            fullres_shp = shp

        backup = False
        import_shp = True
        app = 'seak'

        modls = ['ConservationFeature',  'Cost', 'PuVsCf', 'PuVsCost']
        if import_shp:
            modls.append('PlanningUnit')

        # backup old tables
        if backup:
            print "backing up old tables to /tmp/"
            from django.core.management.commands.dumpdata import Command as Dumper
            for modl in modls:
                try:
                    fix = Dumper.handle(Dumper(), "%s.%s" % (app, modl.lower()), format='json', indent=4)
                except CommandError, message:
                    print "# dumpdata raised a CommandError: %s" % message
                else:
                    fixname = "/tmp/%s_%s.json" % (app, modl.lower())
                    fh = open(os.path.join(fixname), "w+")
                    fh.write(fix)
                    fh.close()

        # Clear them out
        print
        print "Cleaning out old tables"
        ms = [ConservationFeature, Cost, PuVsCf, PuVsCost, DefinedGeography]
        if import_shp:
            ms.append(PlanningUnit)
        for m in ms: 
            m.objects.all().delete()
            assert len(m.objects.all()) == 0

        # Loading planning units from Shapefile
        print "Loading planning units from Shapefile"
        ds = DataSource(shp)
        layer = ds[0]

        # Load ConservationFeatures from xls
        print
        print "Loading ConservationFeatures"
        import xlrd
        book = xlrd.open_workbook(xls)
        sheet = book.sheet_by_name("ConservationFeatures")
        headers = [str(x).strip() for x in sheet.row_values(0)] #returns all the CELLS of row 0,

        fieldnames = ['name', 'uid', 'level1', 'level2', 'level3', 
                      'level4', 'level5', 'dbf_fieldname', 'units']

        assert len(headers) == len(fieldnames)
        for h in range(len(headers)): 
            if headers[h] != fieldnames[h]:
                print "WARNING: field %s is '%s' in the xls file but model is \
                        expecting '%s' ... OK?" % (h, headers[h], fieldnames[h])

        uids = []
        for i in xrange(1, sheet.nrows):
            vals = sheet.row_values(i)
            print vals
            params = dict(zip(fieldnames, vals))
            if params['uid'] in uids:
                raise Exception("Already used UID %s" % params['uid'])
            else:
                uids.append(params['uid'])
            cf = ConservationFeature(**params)
            cf.save()

        cfs = ConservationFeature.objects.all()
        # ensure uniqueness
        level_strings = []
        names = []
        for cf in cfs:
            if cf.level_string in level_strings:
                raise Exception("Levels are not unique: " + cf.level_string)
            if slugify(cf.name) in names:
                raise Exception("Name is not unique: " + cf.name)
            level_strings.append(cf.level_string)
            names.append(slugify(cf.name))
        assert len(cfs) == sheet.nrows - 1

        for cf in cfs:
            fname = cf.dbf_fieldname
            if fname not in layer.fields:
                if find_possible(fname, layer.fields):
                    raise Exception("DBF has no field named `%s`.\n Did you mean `%s`" % (fname, 
                        find_possible(fname, layer.fields)))
                raise Exception("DBF has no field named %s (it IS case sensitive).\n\n %s" % (fname, 
                    layer.fields))
            if fname is None or fname == '':
                print "WARNING: No dbf_fieldname specified for %s" % cf.name
                print "   no info can be extracted from shapefile for this conservation feature"
                continue

        # Load Costs from xls
        print
        print "Loading Costs"
        sheet = book.sheet_by_name("Costs")
        headers = [str(x).strip() for x in sheet.row_values(0)] #returns all the CELLS of row 0,

        fieldnames = ['name', 'uid', 'dbf_fieldname', 'units', 'desc']

        assert len(headers) == len(fieldnames)
        for h in range(len(headers)): 
            if headers[h] != fieldnames[h]:
                print "WARNING: field %s is '%s' in the xls file but model is expecting '%s' ... OK?" % (h, 
                        headers[h], fieldnames[h])

        for i in xrange(1, sheet.nrows):
            vals = sheet.row_values(i)
            print vals
            params = dict(zip(fieldnames, vals))
            c = Cost(**params)
            c.save()

        cs = Cost.objects.all()
        assert len(cs) == sheet.nrows - 1

        for c in cs:
            fname = c.dbf_fieldname
            if fname not in layer.fields:
                if find_possible(fname, layer.fields):
                    raise Exception("DBF has no field named `%s`.\n Did you mean `%s`" % (fname,
                        find_possible(fname, layer.fields)))
                raise Exception("DBF has no field named %s (it IS case sensitive).\n\n %s" % (fname, 
                    layer.fields))

        # Load PU from shpfile
        print
        print "WARNING It is your responsibility to make sure the shapefile projection below \
                matches srid %s" % settings.GEOMETRY_DB_SRID
        print layer.srs

        sheet = book.sheet_by_name("PlanningUnits")
        headers = [str(x.strip()) for x in sheet.row_values(0)] #returns all the CELLS of row 0,
        fieldnames = ['name_field', 'fid_field', 'null_value']
        assert len(headers) == len(fieldnames)
        for h in range(len(headers)): 
            if headers[h] != fieldnames[h]:
                print "WARNING: field %s is '%s' in the xls file but model is expecting \
                       '%s' ... OK?" % (h, headers[h], fieldnames[h])
        for i in xrange(1, sheet.nrows):
            #vals = [str(x.strip()) for x in sheet.row_values(i)]
            vals = sheet.row_values(i)
            params = dict(zip(fieldnames, vals))
 
        mapping = {
            'name' : params['name_field'],
            'fid' : params['fid_field'], 
            'geometry' : 'MULTIPOLYGON',
        }

        NULL_VALUE = params['null_value']

        if "PlanningUnit" in modls:
            lm = LayerMapping(PlanningUnit, shp, mapping, transform=False, encoding='iso-8859-1')
            lm.save(strict=True, verbose=False)
        else:
            print ".... not loading shp"

        pus = PlanningUnit.objects.all()
        assert len(layer) == len(pus)

        print
        print "Generating tile configuration files"
        cfs_with_fields = [x for x in cfs if x.dbf_fieldname is not None and x.dbf_fieldname != '' ]

        xml_template = """<?xml version="1.0"?>
<!DOCTYPE Map [
<!ENTITY google_mercator "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over">
]>
<Map srs="&google_mercator;">
    <Style name="pu" filter-mode="first">
        %(extra_rules)s
        <Rule>
            <PolygonSymbolizer fill="#ffffff" fill-opacity="0.2" />
        </Rule>
    </Style>
    <Style name="pu-outline" filter-mode="first">
        <Rule>
            <LineSymbolizer stroke="#444444" stroke-width="0.5" stroke-opacity="1" stroke-linejoin="round" />
        </Rule>
    </Style>
    <Layer name="layer" srs="&google_mercator;">
        <StyleName>pu-outline</StyleName>
        <StyleName>pu</StyleName>
        <Datasource>
            <Parameter name="type">shape</Parameter>
            <Parameter name="file">%(shppath)s</Parameter>
        </Datasource>
    </Layer>
</Map>""" 
        xml = xml_template % {'shppath': os.path.abspath(fullres_shp), 'extra_rules': ''}

        if not os.path.exists(settings.TILE_CONFIG_DIR):
            os.makedirs(settings.TILE_CONFIG_DIR)

        with open(os.path.join(settings.TILE_CONFIG_DIR, 'planning_units.xml'), 'w') as fh:
            print "  writing planning_units.xml"
            fh.write(xml)

        # Get all dbf fieldnames for the utfgrids
        all_dbf_fieldnames = [cf.dbf_fieldname for cf in cfs_with_fields]
        all_dbf_fieldnames.extend([c.dbf_fieldname for c in cs])
        all_dbf_fieldnames.append(params['name_field'])

        cfg = {
            "cache": {
                "name": "Multi",
                "tiers": [
                    { "name": "Memcache", "servers": ["127.0.0.1:11211"] },
                    { "name": "Disk", "path": "/tmp/stache" }
                ]
            },
            "layers": {
                "planning_units":
                {
                    "provider": 
                     { "name": "mapnik", "mapfile": "planning_units.xml" },
                    "metatile": 
                    { "rows": 4, "columns": 4, "buffer": 64 }
                },
                "utfgrid":
                {
                    "provider":
                    {
                        "class": "TileStache.Goodies.Providers.MapnikGrid:Provider",
                        "kwargs":
                        {
                            "mapfile": "planning_units.xml", 
                            "fields": all_dbf_fieldnames,
                            "layer_index": 0,
                            "scale": 4
                        }
                    }
                }
            }
        }


        print 
        print "create mapnik xml file symbolizing each conservation features and cost"
        numeric_dbf_fieldnames = all_dbf_fieldnames[:]
        numeric_dbf_fieldnames.remove(params['name_field'])
        for fieldname in numeric_dbf_fieldnames:
            vals = layer.get_fields(fieldname)
            vals = [x for x in vals if x >= 0 ]
            breaks = sorted(get_jenks_breaks(vals, 4))
            breaks = [0.000001 if x == 0.0 else x for x in breaks]
            print fieldname, breaks, min(vals), max(vals)
            extra_rules = """
                <Rule>
                    <Filter>([%(fieldname)s] &gt;= %(b3)f)</Filter>
                    <PolygonSymbolizer fill="#CC4C02" fill-opacity="0.7" />
                </Rule>
                <Rule>
                    <Filter>([%(fieldname)s] &gt;= %(b2)f)</Filter>
                    <PolygonSymbolizer fill="#FE9929" fill-opacity="0.7" />
                </Rule>
                <Rule>
                    <Filter>([%(fieldname)s] &gt;= %(b1)f)</Filter>
                    <PolygonSymbolizer fill="#FED98E" fill-opacity="0.7" />
                </Rule>
                <Rule>
                    <Filter>([%(fieldname)s] &gt;= 0)</Filter>
                    <PolygonSymbolizer fill="#FFFFD4" fill-opacity="0.7" />
                </Rule>
            """ % {"fieldname": fieldname, 'b1': breaks[1], 'b2': breaks[2], 'b3': breaks[3]}
            xml = xml_template % {'shppath': os.path.abspath(fullres_shp), 'extra_rules': extra_rules} 
            with open(os.path.join(settings.TILE_CONFIG_DIR, fieldname + '.xml'), 'w') as fh:
                print "  writing %s.xml" % fieldname
                fh.write(xml)

                # add layers (provider = mapnik) for each of the above
                lyrcfg = {
                    "provider": { "name": "mapnik", "mapfile": fieldname + ".xml" },
                    "metatile": { "rows": 4, "columns": 4, "buffer": 64 }
                }
                cfg["layers"][fieldname] = lyrcfg


        with open(os.path.join(settings.TILE_CONFIG_DIR, 'tiles.cfg'), 'w') as fh:
            print "  writing tiles.cfg"
            fh.write(json.dumps(cfg))

        print 
        print "Loading costs and conservation features associated with each planning unit"
        for feature in layer:
            pu = pus.get(fid=feature.get(mapping['fid']))
            for cf in cfs_with_fields:
                amt = feature.get(cf.dbf_fieldname)
                if amt == NULL_VALUE:
                    amt = None
                elif amt < 0:
                    print "WARNING:", cf.dbf_fieldname, "has negative values"
                    amt = 0  # no non-null negatives
                obj = PuVsCf(pu=pu, cf=cf, amount=amt)
                obj.save()

            for c in cs: 
                amt = feature.get(c.dbf_fieldname)
                if amt == NULL_VALUE:
                    amt = None
                elif amt < 0:
                    print "WARNING:", c.dbf_fieldname, "has negative values"
                    amt = 0  # no non-null negatives
                obj = PuVsCost(pu=pu, cost=c, amount=amt)
                obj.save()

        assert len(PuVsCf.objects.all()) == len(pus) * len(cfs_with_fields)
        assert len(PuVsCost.objects.all()) == len(pus) * len(cs)

        # Load Geographies from xls
        print
        print "Loading Defined Geographies"
        sheet = book.sheet_by_name("Geographies")
        headers = sheet.row_values(0) #returns all the CELLS of row 0,
        fieldnames = ['geography', 'dbf_fieldname']

        assert len(headers) == len(fieldnames)
        for h in range(len(headers)): 
            if headers[h] != fieldnames[h]:
                print "WARNING: field %s is '%s' in the xls file but model is expecting '%s' ... OK?" % (h,
                        headers[h], fieldnames[h])

        for i in xrange(1, sheet.nrows):
            vals = sheet.row_values(i)
            print vals
            params = dict(zip(fieldnames, vals))
            dg = DefinedGeography(name=params['geography'])
            dg.save()
            pus = [x.pu for x in PuVsCf.objects.filter(amount__isnull=False, 
                    cf__dbf_fieldname=params['dbf_fieldname'])]
            if len(pus) == 0:
                pus = [x.pu for x in PuVsCost.objects.filter(amount__isnull=False, 
                        cost__dbf_fieldname=params['dbf_fieldname'])]
                if len(pus) == 0:
                    raise Exception(params['geography'] + " has no planning units; check field named " + params['dbf_fieldname'])
            for pu in pus:
                dg.planning_units.add(pu)
            dg.save()

        dgs = DefinedGeography.objects.all()
        assert len(dgs) == sheet.nrows - 1

        # Export the puvscf table to csv directly 
        out = os.path.realpath(os.path.join(settings.MARXAN_TEMPLATEDIR, 'puvcf.dat'))
        print "Exporting the table to %s" % out
        query = """
            COPY (SELECT cf_id as species, pu_id as pu, amount 
                FROM %s_puvscf
                ORDER BY pu)
            TO '%s'
            WITH DELIMITER ','
            CSV HEADER
        """ % (app, out)
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute(query)
        
   
