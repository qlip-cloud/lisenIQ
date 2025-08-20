# Copyright (c) 2025, Mentum Group and Contributors
# See license.txt

import frappe
# import unittest
from frappe.tests.utils import FrappeTestCase

# class Testqp_IQ_AcademicLevel(unittest.TestCase):
# 	pass

class Testqp_IQ_AcademicLevel(FrappeTestCase):
	def test_creation(self):
		level = frappe.new_doc("qp_IQ_AcademicLevel")
		level.title = "Test Level"
		level.abbreviation = "TL"
		level.order = 99
		level.description = "A test academic level."
		
		level.insert() # Guarda el documento en la base de datos

		loaded_level = frappe.get_doc("qp_IQ_AcademicLevel", level.name)
		self.assertEqual(loaded_level.title, "Test Level")
		self.assertEqual(loaded_level.order, 99)

		# Limpiar después de la prueba (FrappeTestCase a menudo maneja esto automáticamente en transacciones)
		# frappe.delete_doc("qp_IQ_AcademicLevel", level.name)