# -*- coding: utf-8 -*-
from odoo import models, fields

class CollegeStudent(models.Model):
    _name = 'college.student'
    _description = 'College Student'

    name = fields.Char(string="Name", required=True)
    roll_no = fields.Char(string="Roll Number")
    department = fields.Char(string="Department")
    address = fields.Char(string="Address")
    email = fields.Char(string="Email")
    date_of_joining = fields.Date(string="Date of Joining") 
    date_of_birth = fields.Date(string="Date of Birth")
    code = fields.Char(string="Code") 
    city = fields.Char(string="City") 
    fees = fields.Float(string="Fees")
    free = fields.Boolean(string="Is Free?", default=False)
    image_1920 = fields.Image(string="Student Image", max_width=1920, max_height=1920)


