"""Predeclared cu2612 schema addition; never relax original contract specifications."""
from copy import deepcopy
APPROVED_NEW={'sizes':5,'slippages':10.0,'rates':0.0,'margin_ratio':0.12}
SYMBOL='cu2612.SHFE'
def normalize_metadata_maps(current,reference,end_day):
 expected={SYMBOL} if end_day=='2026-10-26' else set()
 normalized=deepcopy(current)
 for field in ['sizes','slippages','rates']:
  old,new=reference[field],current[field]
  if any(key not in new or new[key]!=value for key,value in old.items()):raise ValueError('existing_metadata_changed:'+field)
  added=set(new)-set(old)
  if added!=expected:raise ValueError('metadata_additions:'+field+':'+str(sorted(added)))
  for key in added:
   if new[key]!=APPROVED_NEW[field]:raise ValueError('new_metadata_value:'+field)
   del normalized[field][key]
 return normalized

def _parse_margin(text):
 result={}
 for item in str(text).split(','):
  if not item.strip():continue
  key,value=item.split('=',1);key=key.strip()
  if key in result:raise ValueError('duplicate_margin_key:'+key)
  result[key]=float(value)
 return result

def normalize_margin_override(current,reference,end_day):
 old,new=_parse_margin(reference),_parse_margin(current)
 if any(key not in new or new[key]!=value for key,value in old.items()):raise ValueError('existing_margin_changed')
 added=set(new)-set(old);expected={SYMBOL} if end_day=='2026-10-26' else set()
 if added!=expected:raise ValueError('margin_additions:'+str(sorted(added)))
 if added and new[SYMBOL]!=APPROVED_NEW['margin_ratio']:raise ValueError('new_margin_value')
 return reference
