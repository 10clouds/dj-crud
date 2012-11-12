# For compatibility. Chances are, tenclouds.crud will be imported very early by
# by Django, so also import tenclouds.crud.fields which must be imported before
# tastypie.
import tenclouds.crud.fields
