# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing unique constraint on 'Charge', fields ['processor_id']
        db.delete_unique(u'saas_charge', ['processor_id'])

        # Adding model 'CartItem'
        db.create_table(u'saas_cartitem', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('customer', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['saas.Organization'])),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('subscription', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['saas.Plan'])),
            ('recorded', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'saas', ['CartItem'])

        # Adding unique constraint on 'CartItem', fields ['user', 'customer']
        db.create_unique(u'saas_cartitem', ['user_id', 'customer_id'])

        # Adding model 'Coupon'
        db.create_table(u'saas_coupon', (
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'], null=True)),
            ('customer', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['saas.Organization'], null=True)),
            ('created_at', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('code', self.gf('django.db.models.fields.SlugField')(max_length=50, primary_key=True)),
            ('redeemed', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal(u'saas', ['Coupon'])

        # Deleting field 'Plan.customer'
        db.delete_column(u'saas_plan', 'customer_id')

        # Adding field 'Plan.organization'
        db.add_column(u'saas_plan', 'organization',
                      self.gf('django.db.models.fields.related.ForeignKey')(default='', to=orm['saas.Organization']),
                      keep_default=False)


        # Changing field 'Plan.interval'
        db.alter_column(u'saas_plan', 'interval', self.gf('durationfield.db.models.fields.duration.DurationField')())
        # Adding field 'Charge.id'
        db.add_column(u'saas_charge', u'id',
                      self.gf('django.db.models.fields.AutoField')(default=0, primary_key=True),
                      keep_default=False)

        # Adding field 'Charge.description'
        db.add_column(u'saas_charge', 'description',
                      self.gf('django.db.models.fields.TextField')(null=True),
                      keep_default=False)

        # Adding field 'Charge.last4'
        db.add_column(u'saas_charge', 'last4',
                      self.gf('django.db.models.fields.IntegerField')(default=''),
                      keep_default=False)

        # Adding field 'Charge.exp_date'
        db.add_column(u'saas_charge', 'exp_date',
                      self.gf('django.db.models.fields.DateField')(default=datetime.datetime(2013, 11, 3, 0, 0)),
                      keep_default=False)


        # Changing field 'Charge.processor_id'
        db.alter_column(u'saas_charge', 'processor_id', self.gf('django.db.models.fields.SlugField')(max_length=50))

    def backwards(self, orm):
        # Removing unique constraint on 'CartItem', fields ['user', 'customer']
        db.delete_unique(u'saas_cartitem', ['user_id', 'customer_id'])

        # Deleting model 'CartItem'
        db.delete_table(u'saas_cartitem')

        # Deleting model 'Coupon'
        db.delete_table(u'saas_coupon')

        # Adding field 'Plan.customer'
        db.add_column(u'saas_plan', 'customer',
                      self.gf('django.db.models.fields.related.ForeignKey')(default='', to=orm['saas.Organization']),
                      keep_default=False)

        # Deleting field 'Plan.organization'
        db.delete_column(u'saas_plan', 'organization_id')


        # Changing field 'Plan.interval'
        db.alter_column(u'saas_plan', 'interval', self.gf('durationfield.db.models.fields.duration.DurationField')(null=True))
        # Deleting field 'Charge.id'
        db.delete_column(u'saas_charge', u'id')

        # Deleting field 'Charge.description'
        db.delete_column(u'saas_charge', 'description')

        # Deleting field 'Charge.last4'
        db.delete_column(u'saas_charge', 'last4')

        # Deleting field 'Charge.exp_date'
        db.delete_column(u'saas_charge', 'exp_date')


        # Changing field 'Charge.processor_id'
        db.alter_column(u'saas_charge', 'processor_id', self.gf('django.db.models.fields.SlugField')(max_length=50, primary_key=True))
        # Adding unique constraint on 'Charge', fields ['processor_id']
        db.create_unique(u'saas_charge', ['processor_id'])


    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'saas.agreement': {
            'Meta': {'object_name': 'Agreement'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'title': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '150'})
        },
        u'saas.cartitem': {
            'Meta': {'unique_together': "(('user', 'customer'),)", 'object_name': 'CartItem'},
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'customer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Organization']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'recorded': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Plan']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'saas.charge': {
            'Meta': {'object_name': 'Charge'},
            'amount': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'customer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Organization']"}),
            'description': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'exp_date': ('django.db.models.fields.DateField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last4': ('django.db.models.fields.IntegerField', [], {}),
            'processor': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'processor_id': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'state': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'})
        },
        u'saas.coupon': {
            'Meta': {'object_name': 'Coupon'},
            'code': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'primary_key': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'customer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Organization']", 'null': 'True'}),
            'redeemed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']", 'null': 'True'})
        },
        u'saas.organization': {
            'Meta': {'object_name': 'Organization'},
            'belongs': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Organization']", 'null': 'True'}),
            'billing_start': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'contributors': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'contributes'", 'symmetrical': 'False', 'to': u"orm['auth.User']"}),
            'country_name': ('django.db.models.fields.CharField', [], {'max_length': '75'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'locality': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'managers': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'manages'", 'symmetrical': 'False', 'to': u"orm['auth.User']"}),
            'name': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'postal_code': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'processor': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True'}),
            'processor_id': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'region': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'street_address': ('django.db.models.fields.CharField', [], {'max_length': '150'}),
            'subscriptions': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'subscribes'", 'symmetrical': 'False', 'to': u"orm['saas.Plan']"})
        },
        u'saas.plan': {
            'Meta': {'object_name': 'Plan'},
            'amount': ('django.db.models.fields.IntegerField', [], {}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'discontinued_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'interval': ('durationfield.db.models.fields.duration.DurationField', [], {'default': 'datetime.timedelta(30)'}),
            'length': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'next_plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Plan']", 'null': 'True'}),
            'organization': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Organization']"}),
            'setup_amount': ('django.db.models.fields.IntegerField', [], {}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'})
        },
        u'saas.signature': {
            'Meta': {'unique_together': "(('agreement', 'user'),)", 'object_name': 'Signature'},
            'agreement': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Agreement']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_signed': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'saas.transaction': {
            'Meta': {'object_name': 'Transaction'},
            'amount': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'descr': ('django.db.models.fields.TextField', [], {'default': "'N/A'"}),
            'dest_account': ('django.db.models.fields.CharField', [], {'default': "'unknown'", 'max_length': '30'}),
            'dest_organization': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'incoming'", 'to': u"orm['saas.Organization']"}),
            'event_id': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'orig_account': ('django.db.models.fields.CharField', [], {'default': "'unknown'", 'max_length': '30'}),
            'orig_organization': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'outgoing'", 'to': u"orm['saas.Organization']"})
        }
    }

    complete_apps = ['saas']