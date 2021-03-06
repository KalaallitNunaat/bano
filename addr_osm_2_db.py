#!/usr/bin/env python
# coding: UTF-8
import copy
import glob
import gc
import urllib,urllib2
import sys
import shutil
import os,os.path
import psycopg2
from pg_connexion import get_pgc
from pg_connexion import get_pgc_layers
import socket
import time 
import xml.etree.ElementTree as ET
import xml.sax.saxutils as XSS
import zipfile

class Dicts:
	def __init__(self):
		self.lettre_a_lettre = {}
		self.fantoir = {}
		self.code_fantoir_vers_nom_fantoir = {}
		self.osm_insee = {}
		self.abrev_type_voie = {}
		self.expand_titres = {}
		self.abrev_titres = {}
		self.chiffres = []
		self.chiffres_romains = []
		self.mot_a_blanc = []
		self.abrev_titres = {}
		self.noms_voies = {}
		self.ways_osm = {}

	def load_lettre_a_lettre(self):
		self.lettre_a_lettre = {'A':[u'Â',u'À'],
						'C':[u'Ç'],
						'E':[u'È',u'Ê',u'É',u'Ë'],
						'I':[u'Ï',u'Î'],
						'O':[u'Ö',u'Ô'],
						'U':[u'Û',u'Ü']}
	def load_fantoir(self,insee):
		str_query = '''	SELECT 	code_insee||id_voie||cle_rivoli,
								nature_voie||' '||libelle_voie
						FROM	fantoir_voie
						WHERE	code_insee = \''''+insee+'''\' AND
								caractere_annul NOT IN ('O','Q');'''
		cur_fantoir = pgc.cursor()
		cur_fantoir.execute(str_query)
		for c in cur_fantoir:
			self.code_fantoir_vers_nom_fantoir[c[0]] = c[1]
			cle = ' '.join(c[1].replace('-',' ').split())
			cle = normalize(cle)
			self.fantoir[cle] = c[0]
			# self.add_voie('fantoir',cle)
	def load_addr_from_fantoir(self):
		for k in self.fantoir:
			adresses.add_fantoir(k,self.fantoir[k],'FANTOIR')
	def load_chiffres(self):
		self.chiffres = [	['0','ZERO'],
							['1','UN'],
							['2','DEUX'],
							['3','TROIS'],
							['4','QUATRE'],
							['5','CINQ'],
							['6','SIX'],
							['7','SEPT'],
							['8','HUIT'],
							['9','NEUF'],
							[' DIX ',' UNZERO '],
							[' ONZE ',' UNUN '],
                                                        [' DOUZE ',' UNDEUX '],
                                                        [' TREIZE ',' UNTROIS '],
							[' QUATORZE ',' UNQUATRE ']]
	def load_mot_a_blanc(self):
		self.mot_a_blanc = ['DE LA',
							'DU',
							'DES',
							'LE',
							'LA',
							'LES',
							'DE',
							'D']
	def load_expand_titres(self):
		self.expand_titres = [['CPT','CAPITAINE'],
							['GEN','GENERAL']]
	def load_abrev_titres(self):
		self.abrev_titres = [['MARECHAL','MAL'],
							['PRESIDENT','PDT'],
							['GENERAL','GAL'],
							['COMMANDANT','CDT'],
							['CAPITAINE','CAP'],
							['LIEUTENANT','LT'],
							['REGIMENT','REGT'],
							['PROFESSEUR','PROF'],
                            ['JEAN-BAPTISTE','J BTE'],
							['SAINTE','STE'],
							['SAINT','ST']]
	def load_chiffres_romains(self):
		self.chiffres_romains = {	'XXIII':'DEUXTROIS',
									'XXII' :'DEUXDEUX',
									'XXI'  :'DEUXUN',
									'XX'   :'DEUXZERO',
									'XIX'  :'UNNEUF',
									'XVIII':'UNHUIT',
									'XVII' :'UNSEPT',
									'XVI'  :'UNSIX',
									'XV'   :'UNCINQ',
									'XIV'  :'UNQUATRE',
									'XIII' :'UNTROIS',
									'XII'  :'UNDEUX',
									'XI'   :'UNUN',
									'X'    :'UNZERO',
									'IX'   :'NEUF',
									'VIII' :'HUIT',
									'VII'  :'SEPT',
									'VI'   :'SIX',
									'V'    :'CINQ',
									'IV'   :'QUATRE',
									'III'  :'TROIS',
									'II'   :'DEUX',
									'I'    :'UN'}
	def load_abrev_type_voie(self):
		fn = os.path.join(os.path.dirname(__file__), 'abrev_type_voie.txt')
		f = open(fn)
		for l in f:
			c = (l.splitlines()[0]).split('\t')
			self.abrev_type_voie[c[0]] = c[1]
		f.close()
	def load_osm_insee(self):
		finsee_path = os.path.join(os.path.dirname(__file__),'osm_id_ref_insee.csv')
		finsee = open(finsee_path,'r')
		for e in finsee:
			c = (e.splitlines()[0]).split(',')
			self.osm_insee[str(c[1])] = int(c[0])
		finsee.close()
	def load_all(self,code_insee_commune):
		self.load_lettre_a_lettre()
		self.load_abrev_type_voie()
		self.load_expand_titres()
		self.load_abrev_titres()
		self.load_chiffres()
		self.load_chiffres_romains()
		self.load_mot_a_blanc()
		self.load_osm_insee()
		self.load_fantoir(code_insee_commune)
	def add_voie(self,origine,nom):
		cle = normalize(nom)
		if not cle in self.noms_voies:
			self.noms_voies[cle] = {}
		self.noms_voies[cle][origine] = nom
class Node:
	def __init__(self,attribs,tags):
		self.attribs = attribs
		self.tags = tags
		self.sent = False
		self.modified = False
	def get_geom_as_text(self):
		strp = 'ST_PointFromText(\'POINT('+str(self.attribs['lon'])+' '+str(self.attribs['lat'])+')\',4326)'
		return strp
	def move_to(self,lon,lat):
		self.attribs['lon'] = lon
		self.attribs['lat'] = lat
	def get_as_osm_xml_node(self):
		s = "\t<node id="+XSS.quoteattr(self.attribs['id'])
		if self.modified:
			s = s+" action=\"modify\" "
		for a in self.attribs:
			if a != 'id':
				if a == 'user':
					v = XSS.quoteattr(self.attribs[a]).encode('utf8')
				else:
					v = XSS.quoteattr(str(self.attribs[a]).encode('utf8'))
				s = s+" "+a+"="+v
		if len(self.tags) == 0:
			s = s+"/>\n"
		else:
			s = s+">\n"
			for k in sorted(self.tags.viewkeys()):
				s = s+"\t\t<tag k="+XSS.quoteattr(k)+" v="+XSS.quoteattr(self.tags[k]).encode('utf8')+"/>\n"
			s = s+"\t</node>\n"
		return s
class Nodes:
	def __init__(self):
		self.n = {}
		self.min_id = 0
	def load_xml_node(self,xml_node,tags):
		id = str(xml_node.attrib['id'])
		if 'version' not in xml_node.attrib:
			xml_node.attrib['version'] = '0'
		self.n[id]= Node(xml_node.attrib,tags)
		self.min_id = min(self.min_id,int(id))
#		if id == '535300376':
#			os._exit(0)
	def load_new_node_from_xml(self,xml_node,tags):
		n = self.add_new_node(xml_node.attrib,tags)
		return n
	def add_new_node(self,lon,lat,tags):
		id = str(self.min_id - 1)
		attribs = {'lon':lon,'lat':lat,'version':0,'id':id}
		self.n[id] = Node(attribs,tags)
		self.n[id].modified = True
		self.min_id = min(self.min_id,int(id))
		return id
class WayGeom:
	def __init__(self,a_nodes):
		self.a_nodes = a_nodes
	def get_geom_as_linestring_text(self):
		res = '\'LINESTRING('
		a_n = []
		for ni in self.a_nodes:
			a_n.append(str(nodes.n[ni].attribs['lon'])+' '+str(nodes.n[ni].attribs['lat']))
		res = res+','.join(a_n)+')\''
		return res	
	def get_centroid(self):
		x = 0
		y = 0
		for ni in self.a_nodes:
			x += float(nodes.n[ni].attribs['lon'])
			y += float(nodes.n[ni].attribs['lat'])
		x = str(x/len(self.a_nodes))
		y = str(y/len(self.a_nodes))
		return [x,y]	
class Way:
	def __init__(self,geom,tags,attrib,osm_key):
		self.geom = geom
		self.tags = tags
		self.attrib = attrib
		self.modified = False
		self.sent = False
		self.is_valid = True
		
		self.checks_by_osm_key(osm_key)
	def checks_by_osm_key(self,osm_key):
		if osm_key == 'building':
			self.set_wall()
			self.check_valid_building()
		if osm_key == 'parcelle':
			self.collect_adresses()
	def set_wall(self):
		if 'wall' not in self.tags:
			self.wall = 'yes'
		else:
			self.wall = self.tags['wall']
	def check_valid_building(self):
		if len(self.geom.a_nodes) < 4:
			print('*** batiment invalide (au moins 4 points) Voir http://www.osm.org/way/'+self.attrib['id'])
			self.is_valid = False
		if self.is_valid and self.geom.a_nodes[0] != self.geom.a_nodes[-1]:
			print('*** batiment invalide (ouvert) Voir http://www.osm.org/way/'+self.attrib['id'])
			self.is_valid = False
	def collect_adresses(self):
		tmp_addrs = {}
		self.addrs = {}
		for t in self.tags.viewkeys():
			if t[0:4] == 'addr':
				num_addr = t.split(':')[0][4:]
				if not num_addr in tmp_addrs:
					tmp_addrs[num_addr] = {}
				tmp_addrs[num_addr]['addr:'+t.split(':')[1]] = self.tags[t]
		for sa in tmp_addrs.viewkeys():
			if 'addr:street' in tmp_addrs[sa] and 'addr:housenumber' in tmp_addrs[sa]:
				self.addrs[sa] = tmp_addrs[sa]
				dicts.add_voie('parcelle',tmp_addrs[sa]['addr:street'])
	def add_tag(self,k,v):
		self.tags[k] = v
		self.modified = True
	def insert_new_point(self,n_id,offset):
		b_geom = self.geom.a_nodes
		b_geom.insert(offset+1,n_id)
		self.geom.a_nodes = b_geom
		self.modified = True
	def get_as_osm_xml_way(self):
		s_modified = ""
		if self.modified:
			s_modified = "action=\"modify\" "
		s = "\t<way id=\""+self.attrib['id']+"\" "+s_modified
		for a in self.attrib:
			if a == 'id' or a == 'modify':
				continue
			else:
				if a == 'user':
					v = XSS.quoteattr(self.attrib[a]).encode('utf8')
				else:
					v = XSS.quoteattr(str(self.attrib[a]).encode('utf8'))
				#s = s+" "+a+"="+v
				s = s+" "+a.encode('utf8')+"="+v
		s = s+">\n"
		for nl in self.geom.a_nodes:
			s = s+"\t\t<nd ref=\""+str(nl)+"\" />\n"
		for k in sorted(self.tags.viewkeys()):
			s = s+"\t\t<tag k="+XSS.quoteattr(k)+" v="+XSS.quoteattr(self.tags[k]).encode('utf8')+"/>\n"
		s = s+"\t</way>\n"
		return s
	def get_as_SQL_import_building(self):
		str_query = '''INSERT INTO building_'''+code_insee+'''
							(SELECT ST_Transform(ST_SetSRID(ST_MakePolygon(ST_GeomFromText('''+(self.geom.get_geom_as_linestring_text())+''')),4326),2154),
							'''+self.attrib['id']+''',\''''+self.wall+'''\');'''
		return str_query
	def get_as_SQL_import_building_segment(self,indice):
		s_stline = get_line_in_st_line_format([self.geom.a_nodes[indice],self.geom.a_nodes[indice+1]])
		str_query = '''INSERT INTO building_segments_'''+code_insee+''' 
						(SELECT ST_Transform(ST_SetSRID('''+s_stline+''',4326),2154),
						'''+self.attrib['id']+''',
						'''+self.geom.a_nodes[indice]+''',
						'''+self.geom.a_nodes[indice+1]+''',
						'''+str(indice)+''');'''
		return str_query
	def get_as_SQL_import_parcelle(self):
		str_query = ""
		for a in self.addrs:
			str_query = str_query+'''INSERT INTO parcelles_'''+code_insee+''' 
							(SELECT ST_Transform(ST_SetSRID(ST_MakePolygon(ST_GeomFromText('''+(self.geom.get_geom_as_linestring_text())+''')),4326),2154),
							'''+self.attrib['id']+''',\''''+self.addrs[a]['addr:housenumber']+'''\',\''''+normalize(self.addrs[a]['addr:street'])+'''\');'''
		return str_query
class Ways:
	def __init__(self):
		self.w = {'highway':{},
				'building':{},
				'parcelle':{},
				'centroid_building':{}}
	def add_way(self,w,id,osm_key):
		self.w[osm_key][id] = w
class Adresse:
	def __init__(self,node,num,voie,fantoir):
		self.node = node
		self.numero = num
		self.voie = voie
		self.fantoir = fantoir
		self.addr_as_building_way = []
		self.addr_as_node_on_building = []
		self.building_for_addr_node = []
	def add_addr_as_building(self,b_id):
		self.addr_as_building_way = self.addr_as_building_way+[b_id]
	def add_addr_as_node_on_building(self, n_id):
		self.addr_as_node_on_building = self.addr_as_node_on_building+[n_id]
	def add_building_for_addr_node(self,b_id):
		self.building_for_addr_node = self.building_for_addr_node+[b_id]
class Adresses:
	def __init__(self):
		self.a = {}
	def register(self,voie):
		cle = normalize(voie)
		if not cle in self.a:
			self.a[cle] = {'numeros':{},'voies':{},'fantoirs':{}}
	def add_fantoir(self,cle,fantoir,source):
		self.register(cle)
		if len(fantoir) == 10:
			self.a[cle]['fantoirs'][source] = fantoir
		else:
			print(u'Code Fantoir non conforme : {:s}'.format(fantoir))
	def add_voie(self,voie,source):
		cle = normalize(voie)
		self.register(voie)
		self.a[cle]['voies'][source] = voie
	def add_adresse(self,ad):
		""" une adresses est considérée dans la commune si sans Fantoir ou avec un Fantoir de la commune"""
		if (ad.fantoir == '' or (is_valid_fantoir(ad.fantoir) and ad.fantoir[0:5] == code_insee)) and is_valid_housenumber(ad.numero):
			cle = normalize(ad.voie)
			self.add_voie(ad.voie,source)
			self.a[cle]['numeros'][ad.numero] = ad
			if ad.fantoir != '':
				self.a[cle]['fantoirs']['OSM'] = ad.fantoir
		else:
			print(u'adresse rejetée : {:s} {:s}'.format(ad.numero,ad.fantoir))
	def get_cle_by_fantoir(self,fantoir):
		cle = ''
		for c in self.a:
			if 'fantoirs' in self.a[c]:
				if 'OSM' in self.a[c]['fantoirs']:
					if self.a[c]['fantoirs']['OSM'] == fantoir:
						cle = c
						break
				if 'FANTOIR' in self.a[c]['fantoirs']:
					if self.a[c]['fantoirs']['FANTOIR'] == fantoir:
						cle = c
						break
		return cle
	# def has_fantoir(self,cle):
		# res = False
		# if 'fantoir' in self.a[cle]:
			# res = True
		# return res
class Pg_hsnr:
	def __init__(self,d):
		self.x = d[0]
		self.y = d[1]
		self.provenance = d[2]
		self.osm_id = d[3]
		self.numero = d[4]
		self.voie = d[5]
		# self.voie = d[5].decode('utf8')
		self.tags = tags_list_as_dict(d[6])
		self.fantoir = ''
		if self.provenance == '3' or self.provenance == '4':
			self.set_street_name()
		self.set_fantoir()
	def set_street_name(self):
		# dtags = tags_list_as_dict(self.tags)
		if 'type' in self.tags and self.tags['type'] == 'associatedStreet' and 'name' in self.tags:
			self.voie = self.tags['name']
			# print('******'+self.voie+' $$$$$$$$ '+self.tags['name'])
		# str_tags = '#'+'#'.join(self.tags)+'#'
		# s1 = str_tags.split('type#associatedStreet#')
		# if len(s1) == 2:
			# s2 = s1.split(
		# if str_tags.find('type#associatedStreet') in self.tags and str_tags.find('name#'):
			# self.voie = str_tags.split('name#')[1].split('#')[0]
	def set_fantoir(self):
		if 'ref:FR:FANTOIR' in self.tags and len(self.tags['ref:FR:FANTOIR']) == 10:
			self.fantoir = self.tags['ref:FR:FANTOIR']
def batch_start_log(source,etape,code_cadastre):
	t = time.localtime()
	th =  time.strftime('%d-%m-%Y %H:%M:%S',t)
	t = round(time.mktime(t),0)
	pgc = get_pgc()
	cur = pgc.cursor()
	whereclause = 'cadastre_com = \'{:s}\' AND source = \'{:s}\' AND etape = \'{:s}\''.format(code_cadastre,source,etape)
	str_query = 'INSERT INTO batch_historique (SELECT * FROM batch WHERE {:s});'.format(whereclause)
	str_query = str_query+'DELETE FROM batch WHERE {:s};'.format(whereclause)
	str_query = str_query+'INSERT INTO batch (source,etape,timestamp_debut,date_debut,dept,cadastre_com,nom_com,nombre_adresses) SELECT \'{:s}\',\'{:s}\',{:f},\'{:s}\',dept,cadastre_com,nom_com,0 FROM code_cadastre WHERE cadastre_com = \'{:s}\';'.format(source,etape,t,th,code_cadastre)
	str_query = str_query+'COMMIT;'
	#print(str_query)
	cur.execute(str_query)
	# print(str_query)
	str_query = 'SELECT id_batch::integer FROM batch WHERE {:s};'.format(whereclause)
	cur.execute(str_query)
	c = cur.fetchone()
	return c[0]
def batch_end_log(nb,batch_id):
	pgc = get_pgc()
	cur = pgc.cursor()
	t = time.localtime()
	th =  time.strftime('%d-%m-%Y %H:%M:%S',t)
	whereclause = 'id_batch = {:d}'.format(batch_id)
	str_query = 'UPDATE batch SET nombre_adresses = {:d},date_fin = \'{:s}\' WHERE {:s};COMMIT;'.format(nb,th,whereclause)
	# print(str_query)
	cur.execute(str_query)
def get_part_debut(s,nb_parts):
	resp = ''
	if get_nb_parts(s) > nb_parts:
		resp = ' '.join(s.split()[0:nb_parts])
	return resp
def get_nb_parts(s):
	return len(s.split())
def replace_type_voie(s,nb):
	sp = s.split()
	spd = ' '.join(sp[0:nb])
	spf = ' '.join(sp[nb:len(sp)])
	s = dicts.abrev_type_voie[spd]+' '+spf
	return s
def is_valid_housenumber(hsnr):
	is_valid = True
	if len(hsnr.encode('utf8')) > 10:
		is_valid = False
	return is_valid
def is_valid_fantoir(f):
	res = True
	if len(f) != 10:
		res = False
	return res
def normalize(s):
	# print(s)
	# s = s.encode('ascii','ignore')
	s = s.upper()				# tout en majuscules
	s = s.replace('-',' ')		# separateur espace
	s = s.replace('\'',' ')		# separateur espace
	s = s.replace('/',' ')		# separateur espace
	s = s.replace(':',' ')		# separateur deux points
	s = ' '.join(s.split())		# separateur : 1 espace
	for l in iter(dicts.lettre_a_lettre):
		for ll in dicts.lettre_a_lettre[l]:
			s = s.replace(ll,l)
	s = s.encode('ascii','ignore')
	
	# type de voie
	abrev_trouvee = False
	p = 0
	while (not abrev_trouvee) and p < 3:
		p+= 1
		if get_part_debut(s,p) in dicts.abrev_type_voie:
			s = replace_type_voie(s,p)
			abrev_trouvee = True

	# ordinal
	s = s.replace(' EME ','EME ')

	# chiffres
	for c in dicts.chiffres:
		s = s.replace(c[0],c[1])

	# articles
	for c in dicts.mot_a_blanc:
		s = s.replace(' '+c+' ',' ')

	# titres, etc.
	for r in dicts.expand_titres:
		s = s.replace(' '+r[0]+' ',' '+r[1]+' ')
	for r in dicts.abrev_titres:
		s = s.replace(' '+r[0]+' ',' '+r[1]+' ')

	# chiffres romains
	sp = s.split()

	if sp[-1] in dicts.chiffres_romains:
		sp[-1] = dicts.chiffres_romains[sp[-1]]
		s = ' '.join(sp)
			
	return s
def get_line_in_st_line_format(nodelist):
	s = 'ST_LineFromText(\'LINESTRING('
	l_coords = []
	for id in nodelist:
		l_coords.append(str(nodes.n[id].attribs['lon'])+' '+str(nodes.n[id].attribs['lat']))
	s = s+','.join(l_coords)+')\')'
	return s
def tags_list_as_dict(ltags):
	# print(ltags)
	res = {}
	for i in range(0,int(len(ltags)/2)):
		res[ltags[i*2]] = ltags[i*2+1]
	# print('res : ')
	# print(res)
	return res
def get_best_fantoir(cle):
	res = ''
	if 'FANTOIR' in adresses.a[cle]['fantoirs']:
		res = adresses.a[cle]['fantoirs']['FANTOIR']
	if 'OSM' in adresses.a[cle]['fantoirs']:
		res = adresses.a[cle]['fantoirs']['OSM']
	return res
def get_code_cadastre_from_insee(insee):
	str_query = 'SELECT cadastre_com FROM code_cadastre WHERE insee_com = \'{:s}\';'.format(insee)
	cur = pgc.cursor()
	cur.execute(str_query)
	for c in cur:
		code_cadastre = c[0]
	return code_cadastre
def get_data_from_pg(data_type,insee):
	fq = open('sql/{:s}.sql'.format(data_type),'rb')
	str_query = fq.read().replace('__com__',insee)
	fq.close()
	# print(str_query)

	cur = pgcl.cursor()
	cur.execute(str_query)
	res = cur.fetchall()
	cur.close()
	return res
def load_highways_from_pg_osm(insee):
	data = get_data_from_pg('highway_insee',insee)
	for lt in data:
		l = list(lt)
		name = l[0].decode('utf8')
		if len(name) < 2:
			continue
		cle = normalize(name)
		fantoir = ''
		if len(l)>1:
			if l[1] != None and l[1][0:5] == insee:
				fantoir = l[1]
				adresses.add_fantoir(cle,l[1],'OSM')
		if len(l)>2 and fantoir == '':
			if l[2] != None and l[2][0:5] == insee:
				fantoir = l[2]
				adresses.add_fantoir(cle,l[2],'OSM')
		if len(l)>3 and fantoir == '':
			if l[3] != None and l[3][0:5] == insee:
				fantoir = l[3]
				adresses.add_fantoir(cle,l[3],'OSM')
		adresses.add_voie(name,'OSM')
def load_hsnr_from_pg_osm(insee):
	data = get_data_from_pg('hsnr_insee',insee)
	for l in data:
		oa = Pg_hsnr(list(l))
		n = Node({'id':oa.osm_id,'lon':oa.x,'lat':oa.y},{})
		# print(list(l))
		if oa.voie == None:
			# print('***none******')
			continue
		# adresses.add_adresse(Adresse(n,oa.numero,oa.voie.decode('utf8').encode('utf8'),oa.fantoir))
		adresses.add_adresse(Adresse(n,oa.numero.decode('utf8'),oa.voie.decode('utf8'),oa.fantoir))
def add_fantoir_to_hsnr():
	for v in adresses.a:
		if v in dicts.fantoir:
			adresses.a[v]['fantoirs']['FANTOIR'] = dicts.fantoir[v]
			adresses.a[v]['voies']['FANTOIR'] = dicts.code_fantoir_vers_nom_fantoir[dicts.fantoir[v]]
		else:
			if 'OSM' in adresses.a[v]['fantoirs']:
				if adresses.a[v]['fantoirs']['OSM'] in dicts.code_fantoir_vers_nom_fantoir:
					adresses.a[v]['voies']['FANTOIR'] = dicts.code_fantoir_vers_nom_fantoir[adresses.a[v]['fantoirs']['OSM']]
def purge_pg_tables(code_insee):
	str_query = '''SELECT	tablename
					FROM 	pg_tables
					WHERE	upper(tablename) like \'%'''+code_insee.upper()+'''\';'''
	cur_sql = pgc.cursor()
	cur_sql.execute(str_query)
	str_del = ''
	for c in cur_sql:
		str_del = str_del+'DROP TABLE IF EXISTS '+c[0]+' CASCADE;'
	cur_sql.execute(str_del)
	cur_sql.close()
def	load_to_db(adresses):
	sload = 'DELETE FROM cumul_adresses WHERE insee_com = \'{:s}\' AND source = \'{:s}\';\n'.format(code_insee,source)
	cur_insert = pgc.cursor()
	cur_insert.execute(sload)
	nb_rec = 0
	for v in adresses.a:
		# print(v)
		sload = 'INSERT INTO cumul_adresses (geometrie,numero,voie_cadastre,voie_osm,fantoir,insee_com,cadastre_com,dept,code_postal,source) VALUES'
		a_values = []
		if not adresses.a[v]['numeros']:
			continue
		# street_name = v.title().encode('utf8')
		street_name_cadastre = ''
		street_name_osm = ''
		street_name_fantoir = ''
		cle_fantoir = get_best_fantoir(v)
		# if 'adresse' in dicts.noms_voies[v]:
			# street_name_cadastre = dicts.noms_voies[v]['adresse'].encode('utf8')
		if 'OSM' in adresses.a[v]['voies']:
			street_name_osm =  adresses.a[v]['voies']['OSM'].encode('utf8')
			# print(street_name_osm)
		if 'FANTOIR' in adresses.a[v]['voies']:
			street_name_fantoir =  adresses.a[v]['voies']['FANTOIR'].encode('utf8')
		if street_name_osm == '' and street_name_fantoir == '':
			print('****** voies muettes '+v)
	# nodes
		for num in adresses.a[v]['numeros']:
			numadresse = adresses.a[v]['numeros'][num]
			a_values.append('(ST_PointFromText(\'POINT({:s} {:s})\', 4326),\'{:s}\',\'{:s}\',\'{:s}\',\'{:s}\',\'{:s}\',\'{:s}\',\'{:s}\',\'{:s}\',\'{:s}\')'.format(numadresse.node.attribs['lon'],numadresse.node.attribs['lat'],numadresse.numero.encode('utf8'),street_name_fantoir.replace("'","''"),street_name_osm.replace("'","''"),cle_fantoir,code_insee,code_cadastre,code_dept,'',source))
			nb_rec +=1
		sload = sload+','.join(a_values)+';COMMIT;'
		# print(sload)	
		cur_insert.execute(sload)
	
	batch_end_log(nb_rec,batch_id)
def main(args):
	debut_total = time.time()
	if len(args) < 2:
		print('USAGE : python addr_osm_2_db.py <code INSEE>')
		os._exit(0)

	global source,batch_id
	global pgc,pgcl
	global code_insee,code_cadastre,code_dept
	global dicts
	global nodes,ways,adresses

	source = 'OSM'

	pgc = get_pgc()
	pgcl = get_pgc_layers()
	
	code_insee = args[1]
	code_cadastre = get_code_cadastre_from_insee(code_insee)
	code_dept = '0'+code_insee[0:2]
	if code_insee[0:2] == '97':
		code_dept = code_insee[0:3]
	
	batch_id = batch_start_log(source,'loadCumul',code_cadastre)
	
	adresses = Adresses()
	dicts = Dicts()
	dicts.load_all(code_insee)
	
	load_highways_from_pg_osm(code_insee)
	load_hsnr_from_pg_osm(code_insee)
	add_fantoir_to_hsnr()
	load_to_db(adresses)

	fin_total = time.time()
	print('Execution en '+str(int(fin_total - debut_total))+' s.')
	# mode 1 : addr:housenumber comme tag du building
	#			sinon point adresse seul à la place fournie en entree
	# mode 2 : addr:housenumber comme point à mi-longueur du plus proche coté du point initial
	#			sinon point adresse seul à la place fournie en entree
if __name__ == '__main__':
    main(sys.argv)


