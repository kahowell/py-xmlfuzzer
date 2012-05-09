#!/usr/bin/env python3
#    Copyright (c) 2012, Kevin Howell
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#    
#    Additional terms:
#    Redistributions of source code must retain the above copyright notice, as
#    well as the list of contributors. (In AUTHORS file).
#
#    Redistributions in binary form must reproduce the above copyright notice.
import xml.dom.minidom as minidom
from xml.dom import *
import sys
import random
import string
import urllib.request
import os.path
import threading

XSDNS = 'http://www.w3.org/2001/XMLSchema'
loadedSchemas = {}
prefixMap = {'xml' : XML_NAMESPACE}
baseTypes = ['xs:boolean', 'xs:float', 'xs:anyURI', 'xs:string', 'xs:date', 'xs:NMTOKEN', 'xs:dateTime', 'xs:ID', 'xs:token', 'xs:Name', 'xs:NCName', 'xs:double', 'xs:unsignedLong', 'xs:hexBinary', 'xs:integer']
DEFAULT_MAX_STR_LEN = 4000
DEFAULT_MAX_NUM_ELEM = 5

class Schema: pass

# TODO: add different length strategies
def chooseLength(lowerBound, upperBound):
	return random.randint(int(lowerBound),int(upperBound))

def generateBaseTypeAttribute(schema, name, type):
	prefix = determinePrefix(schema)
	attribute = newDoc.createAttributeNS(schema['targetNamespace'], prefix + name)
	attribute.value = generateBaseType(type)
	return attribute

def generateBaseType(type, restrictions = None):
	if type == 'xs:anyURI':
		return 'http://www.example.com'
	if type == 'xs:string':
		minLength = 1
		maxLength = DEFAULT_MAX_STR_LEN
		
		if restrictions:
			if restrictions.minLength:
				minLength = restrictions.minLength[0]
			if restrictions.maxLength:
				maxLength = restrictions.maxLength[0]
			if restrictions.length:
				minLength = maxLength = restrictions.length[0]
			if restrictions.enumerations:
				return random.choice(restrictions.enumerations)
		return randomString(chooseLength(minLength, maxLength))
	if type == 'xs:NMTOKEN' or type == 'xs:token' or type == 'xs:Name' or type == 'xs:NCName' or type == 'xs:ID':
		return randomString(16)
	if type == 'xs:date':
		return '%4.4i-%2.2i-%2.2i' % (random.randint(1970,2100), random.randint(1,12), random.randint(1,30))
	if type == 'xs:dateTime':
		return '%4.4i-%2.2i-%2.2iT%2.2i:%2.2i:%2.2i' % (random.randint(1970,2100), random.randint(1,12), random.randint(1,30), random.randint(0,23), random.randint(0,59), random.randint(0,59))
	if type == 'xs:double' or type == 'xs:float':
		return str(random.random())
	if type == 'xs:unsignedLong':
		return str(random.randint(0,32000))
	if type == 'xs:integer' or type == 'xs:long':
		return str(random.randint(-16000, 16000))
	if type == 'xs:hexBinary':
		return 'TODO: implement hexBinary'
	if type == 'xs:boolean':
		return random.choice(['true', 'false'])

def randomString(strLen):
	return ''.join(random.choice(string.digits + string.ascii_letters + string.punctuation + ' \t') for x in range(strLen))

class Restrictions:
	def __init__(self):
		self.length = []
		self.minLength = []
		self.maxLength = []
		self.enumerations = []

def findSimpleType(schema, name):
	if name in schema.simpleTypes.keys():
		return schema.simpleTypes[name]
	else: # search imported namespaces
		targetNamespace = None
		if len(name.split(':')) > 1:
			targetNamespace = prefixMap[name.split(':')[0]]
			name = name.split(':')[-1]
		for refSchema in schema.refSchemas:
			if name in refSchema.simpleTypes.keys():
				if targetNamespace is None or targetNamespace == refSchema.targetNamespace:
					return refSchema.simpleTypes[name]
	raise Exception('Cannot find definition of simpleType "%s"' % name)

def generateList(schema, list, restrictions = None):
	typeName = list.attributes['itemType'].value
	
	lowerBound = 1
	if restrictions.minLength:
		lowerBound = restrictions.minLength[0]
		
	upperBound = 5
	if restrictions.maxLength:
		upperBound = restrictions.maxLength[0]
	
	length = chooseLength(lowerBound, upperBound)
	print('generating', length, 'items')
	list = []
	for i in range(length):
		list.append(generateValue(schema, typeName)[0].data)
	print ('items:', list)
	return [newDoc.createTextNode(' '.join(list))]
	

def generateSimpleType(schema, simpleType, restrictions = None):
	print('generating simpleType:', simpleType)
	base = None
	length = []
	minLength = []
	maxLength = []
	enumerations = []
	try:
		restriction = [node for node in simpleType.childNodes if node.localName == 'restriction'][0]
		length = [node for node in restriction.childNodes if node.localName == 'length']
		minLength = [node for node in restriction.childNodes if node.localName == 'minLength']
		maxLength = [node for node in restriction.childNodes if node.localName == 'maxLength']
		enumerations = [node for node in restriction.childNodes if node.localName == 'enumeration']
		if [node for node in restriction.childNodes if node.localName == 'pattern']:
			print('WARNING: simpleType %s has a pattern restriction' % simpleType.attributes['name'].value)
		base = restriction.attributes['base'].value
	except:
		if not base:
			try:
				base = filterChildren(simpleType, 'extension')[0].attributes['base'].value
			except:
				pass
	prefix = determinePrefix(schema)
	lowerBound = 0
	upperBound = DEFAULT_MAX_STR_LEN
	if restrictions is None:
		restrictions = Restrictions()
	restrictions.length.extend([restriction.attributes['value'].value for restriction in length])
	restrictions.minLength.extend([restriction.attributes['value'].value for restriction in minLength])
	restrictions.maxLength.extend([restriction.attributes['value'].value for restriction in maxLength])
	if not restrictions.enumerations:
		restrictions.enumerations = [enumeration.attributes['value'].value for enumeration in enumerations]
		
	if filterChildren(simpleType, 'list'):
		value = generateList(schema, filterChildren(simpleType, 'list')[0], restrictions)[0].data
	
	elif base in baseTypes:
		value = generateBaseType(base, restrictions)
	else:
		print('Generating base "%s"' % base)
		return generateSimpleType(schema, findSimpleType(schema, base), restrictions)
	return [newDoc.createTextNode(str(value))]

# TODO: additional choosing strategies (always/never)
def chooseBool():
	return random.choice([True, False])

def generateAttributes(schema, element):
	attributes = []
	for attribute in [attribute for attribute in element.childNodes if attribute.localName == 'attribute']:
		if 'name' not in attribute.attributes.keys():
			if attribute.attributes['ref'].value in schema['attributes'].keys():
				if 'use' not in attribute.attributes.keys() or attribute.attributes['use'].value != 'optional' or chooseBool():
					attributes.append(generateAttribute(schema, schema['attributes'][attribute.attributes['ref'].value]))
			else: # search imported namespaces
				name = attribute.attributes['ref'].value.split(':')[-1]
				oldLength = len(attributes)
				for schema in schema['refSchemas']:
					if name in schema['attributes'].keys():
						if 'use' not in attribute.attributes.keys() or attribute.attributes['use'].value != 'optional' or random.choice([True, False]):
							attributes.append(generateAttribute(schema, schema['attributes'][name]))
				if len(attributes) == oldLength:
					raise Exception('Cannot find attribute with name "%s"' % attribute.attributes['ref'].value)
		else:		
			if 'use' not in attribute.attributes.keys() or attribute.attributes['use'].value != 'optional' or random.choice([True, False]):
				attributes.append(generateAttribute(schema, attribute))
	#print('DEBUG:', dict(zip([attribute.attributes['name'].value if 'name' in attribute.attributes.keys() else attribute.attributes['ref'].value for attribute in complexType.childNodes if attribute.localName == 'attribute'], [attributes])))
	return attributes

def minMaxOccurs(element):	
	minOccurs = 1
	maxOccurs = 1
	if 'minOccurs' in element.attributes.keys():
		minOccurs = element.attributes['minOccurs'].value
	if 'maxOccurs' in element.attributes.keys():
		maxOccurs = element.attributes['maxOccurs'].value
	if (maxOccurs == 'unbounded'):
		maxOccurs = DEFAULT_MAX_NUM_ELEM
	return minOccurs, maxOccurs

def generateElements(schema, element):
	if 'name' not in element.attributes.keys():
		return generateElementRefInstance(schema, element)
	minLength, maxLength = minMaxOccurs(element)
	numberElements = chooseLength(minLength, maxLength)
	elements = []
	for i in range(numberElements):
		elements.append(generateElement(schema, element))
	return elements

def processSequence(schema, sequence):
	minLength, maxLength = minMaxOccurs(sequence)
	numberElements = chooseLength(minLength, maxLength)
	elements = []
	for i in range(numberElements):
		for node in sequence.childNodes:
			if node.localName == 'element':
				elements.extend(generateElements(schema, node))
			if node.localName == 'sequence':
				elements.extend(processSequence(schema, node))
			if node.localName == 'choice':
				elements.extend(processChoice(schema, node))
			if node.localName == 'group':
				elements.extend(processGroup(schema, node))
	return elements

def processGroup(schema, group):
	minLength, maxLength = minMaxOccurs(group)
	numberElements = chooseLength(minLength, maxLength)
	elements = []
	for i in range(numberElements):
		for node in group.childNodes:
			if node.localName == 'element':
				elements.extend(generateElements(schema, node))
			if node.localName == 'sequence':
				elements.extend(processSequence(schema, node))
			if node.localName == 'choice':
				elements.extend(processChoice(schema, node))
			if node.localName == 'group':
				elements.extend(processGroup(schema, node))
	return elements

def processChoice(schema, choice):
	minLength, maxLength = minMaxOccurs(choice)
	numberElements = chooseLength(minLength, maxLength)
	elements = []
	for i in range(numberElements):
		node = random.choice(choice.childNodes)
		if node.localName == 'element':
			elements.extend(generateElements(schema, node))
		if node.localName == 'sequence':
			elements.extend(processSequence(schema, node))
		if node.localName == 'choice':
			elements.extend(processChoice(schema, node))
		if node.localName == 'group':
			elements.extend(processGroup(schema, node))
	return elements

def generateElementRefInstance(schema, element):
	minOccurs, maxOccurs = minMaxOccurs(element)
	name = element.attributes['ref'].value
	prototype = None
	if name in schema.elements.keys():
		prototype = schema.elements[name]
	else: # search imported namespaces
		targetNamespace = None
		if len(name.split(':')) > 1:
			targetNamespace = prefixMap[name.split(':')[0]]
			name = name.split(':')[-1]
		for refSchema in schema.refSchemas:
			if name in refSchema.elements.keys():
				if targetNamespace is None or targetNamespace == refSchema.targetNamespace:
					prototype = refSchema.elements[name]
					schema = refSchema
	if prototype is None:
		raise Exception('Cannot find element with name "%s"' % element.attributes['ref'].value)
	else:
		elements = []
		for i in range(chooseLength(minOccurs, maxOccurs)):
			elements.append(generateElement(schema, prototype))
		return elements

def generateValue(schema, typeName):
	print('type:', typeName)
	if typeName in baseTypes:
		return [newDoc.createTextNode(generateBaseType(typeName))]
	elif typeName in schema.simpleTypes.keys():
		return generateSimpleType(schema, schema.simpleTypes[typeName])
	elif typeName in schema.complexTypes.keys():
		return generateComplexType(schema, schema.complexTypes[typeName])
	else: # search imported namespaces
		targetNamespace = None
		if len(typeName.split(':')) > 1:
			targetNamespace = prefixMap[typeName.split(':')[0]]
			typeName = typeName.split(':')[-1]
		for refSchema in schema.refSchemas:
			if targetNamespace is None or targetNamespace == refSchema.targetNamespace:
				if typeName in refSchema.simpleTypes.keys():
					return generateSimpleType(refSchema, refSchema.simpleTypes[typeName])
				elif typeName in refSchema.complexTypes.keys():
					return generateComplexType(refSchema, refSchema.complexTypes[typeName])
	raise Exception('Cannot find type with name "%s"' % typeName)

def generateRefAttribute(schema, attribute):
	name = attribute.attributes['ref'].value
	if name in schema.attributes.keys():
		prototype = schema.attributes[name]
	else: # search imported namespaces
		targetNamespace = None
		if len(name.split(':')) > 1:
			targetNamespace = prefixMap[name.split(':')[0]]
			name = name.split(':')[-1]
		for refSchema in schema.refSchemas:
			if name in refSchema.attributes.keys():
				if targetNamespace is None or targetNamespace == refSchema.targetNamespace:
					prototype = refSchema.attributes[name]
					schema = refSchema
	if prototype is None:
		raise Exception('Cannot find attribute with name "%s"' % attribute.attributes['ref'].value)
	else:
		return generateAttribute(schema, prototype)	
		
def generateAttribute(schema, attribute):
	if 'ref' in attribute.attributes.keys():
		return generateRefAttribute(schema, attribute)
	attributeElement = newDoc.createAttributeNS(schema.targetNamespace, attribute.attributes['name'].value)
	print(attribute)
	attributeElement.value = generateValue(schema, attribute.attributes['type'].value)[0].data
	return attributeElement

def generateComplexType(schema, complexType):
	minOccurs, maxOccurs = minMaxOccurs(complexType)
	elements = []
	for attribute in filterChildren(complexType, 'attribute'):
		if ('use' in attribute.attributes.keys() and attribute.attributes['use'].value == 'required') or chooseBool():
			if 'ref' in attribute.attributes.keys():
				generateRefAttribute(schema, attribute)
			else:
				elements.append(generateAttribute(schema, attribute))
	for i in range(chooseLength(minOccurs, maxOccurs)):
		for sequence in filterChildren(complexType, 'sequence'):
			elements.extend(processSequence(schema, sequence))
		for element in filterChildren(complexType, 'element'):
			elements.extend(generateElements(schema, element))
		for group in filterChildren(complexType, 'group'):
			elements.extend(processGroup(schema, group))
		for choice in filterChildren(complexType, 'choice'):
			elements.extend(processChoice(schema, choice))
		for simpleType in filterChildren(complexType, 'simpleType'):
			elements.extend(generateSimpleType(schema, simpleType))
		for simpleContent in filterChildren(complexType, 'simpleContent'):
			elements.extend(generateSimpleType(schema, simpleContent))
		if filterChildren(complexType, 'any'):
			print('WARNING: this program does not support xs:any (yet).')
	return elements

def generateElement(schema, element):
	'''generate a single instance of an element - does not handle referenced elements'''
	prefix = determinePrefix(schema)
	newElement = newDoc.createElementNS(schema.targetNamespace, prefix + element.attributes['name'].value)
	elements = []
	if 'type' in element.attributes:
		elements.extend(generateValue(schema, element.attributes['type'].value))
	for complexType in filterChildren(element, 'complexType'):
		elements.extend(generateComplexType(schema, complexType))
	for simpleType in filterChildren(element, 'simpleType'):
		elements.extend(generateSimpleType(schema, simpleType))
	for element in elements:
		if element.nodeType == Node.ATTRIBUTE_NODE:
			newElement.setAttributeNode(element)
		else:
			newElement.appendChild(element)
	return newElement

def determinePrefix(schema):
	prefix = ''
	if rootSchema.targetNamespace != schema.targetNamespace:
		prefix = {value : key for key, value in prefixMap.items()}[schema['targetNamespace']] + ':'
	return prefix

def fetchSchemaFile(url):
	schemaFilename = url.split('/')[-1]
	print("Looking for %s" % schemaFilename)
	if os.path.isfile(schemaFilename):
		print("%s was present" % schemaFilename)
	else:
		print("%s not found... retrieving" % schemaFilename)
		urllib.request.urlretrieve(url, schemaFilename)
	return schemaFilename

def loadSchema(schemaUrl):
	'''Loads the schema into the target dictionary'''
	global loadedSchemas
	global prefixMap
	if schemaUrl in loadedSchemas.keys():
		return loadedSchemas[schemaUrl]
	target = Schema()
	filename = fetchSchemaFile(schemaUrl)
	xsdRoot = minidom.parse(filename).documentElement
	target.defaultNamespace = xsdRoot.attributes['xmlns'].value if 'xmlns' in xsdRoot.attributes.keys() else None
	target.targetNamespace = xsdRoot.attributes['targetNamespace'].value
	target.namespaces = {}
	for namespace in [namespace for namespace in xsdRoot.attributes.keys() if namespace.startswith('xmlns') and len(namespace.split(':')) > 1]:
		target.namespaces[namespace.split(':')[-1]] = xsdRoot.attributes[namespace].value
	prefixMap.update(target.namespaces)
	target.elements = {element.attributes['name'].value : element for element in filterChildren(xsdRoot, 'element')}
	if (filterChildren(xsdRoot, 'element')):
		target._firstElement = filterChildren(xsdRoot, 'element')[0]
	target.attributes = {attribute.attributes['name'].value : attribute for attribute in filterChildren(xsdRoot, 'attribute')}
	target.simpleTypes = {simpleType.attributes['name'].value : simpleType for simpleType in filterChildren(xsdRoot, 'simpleType')}
	target.complexTypes = {complexType.attributes['name'].value : complexType for complexType in filterChildren(xsdRoot, 'complexType')}
	target.imports = xsdRoot.getElementsByTagNameNS(XSDNS, 'import')
	# load by schemaLocation, falling back to namespace
	target.refSchemas = [loadSchema(schema.attributes['schemaLocation'].value) if 'schemaLocation' in schema.attributes.keys() else loadSchema(schema.attributes['namespace'].value) for schema in target.imports]
	loadedSchemas[schemaUrl] = target
	return target

def filterChildren(element, name):
	return [element for element in element.childNodes if element.localName == name]

def die():
	print('ran for too long. quitting.')
	for thread in threading.enumerate():
		if thread.isAlive():
			try:
				thread._stop()
			except:
				pass
	sys.exit(1)

if __name__ == '__main__':
	global xsdDoc
	global newDoc
	global rootSchema
	if len(sys.argv) < 2:
		print('Usage: %s filename [rootElement]' % sys.argv[0])
		sys.exit(1)
		
	# setup max runtime
	die = threading.Timer(2.0, die)
	die.daemon = True
	die.start()
	# find root element...
	rootSchema = loadSchema(sys.argv[1])
	if len(sys.argv) > 2:
		root = rootSchema.elements[sys.argv[2]]
	else:
		root = rootSchema._firstElement
	newDoc = minidom.Document()
	newDoc.appendChild(generateElement(rootSchema, root))
	die.cancel()
	newDoc.writexml(open('out.xml', 'w'), newl='\n', addindent='\t', encoding='utf-8')
