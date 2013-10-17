# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding M2M table for field subscriptions on 'Organization'
        db.create_table(u'saas_organization_subscriptions', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('organization', models.ForeignKey(orm[u'saas.organization'], null=False)),
            ('plan', models.ForeignKey(orm[u'saas.plan'], null=False))
        ))
        db.create_unique(u'saas_organization_subscriptions', ['organization_id', 'plan_id'])


    def backwards(self, orm):
        # Removing M2M table for field subscriptions on 'Organization'
        db.delete_table('saas_organization_subscriptions')


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
        u'saas.charge': {
            'Meta': {'object_name': 'Charge'},
            'amount': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'customer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Organization']"}),
            'processor': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'processor_id': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'primary_key': 'True'}),
            'state': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'})
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
            'customer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Organization']"}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'discontinued_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'interval': ('durationfield.db.models.fields.duration.DurationField', [], {'null': 'True'}),
            'length': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'next_plan': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['saas.Plan']", 'null': 'True'}),
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