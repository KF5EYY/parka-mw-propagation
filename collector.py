#!/usr/bin/env python3
"""Parka propagation collector. Python standard library only."""
import csv, json, os, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
BASE='https://services.swpc.noaa.gov'
URLS={
 'kp':BASE+'/products/noaa-planetary-k-index.json',
 'speed':BASE+'/products/summary/solar-wind-speed.json',
 'mag':BASE+'/products/summary/solar-wind-mag-field.json',
 'proton':BASE+'/json/goes/primary/integral-protons-1-day.json',
}
FIELDS=['collected_at','kp','kp_at','wind_kms','wind_at','bz_nt','bz_at','protons_pfu','protons_at','quality','errors']
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'ParkaMWDashboard/1.0 (scientific monitoring)','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
def num(v):
 try:
  x=float(v)
  return x if -1e8 < x < 1e8 else None
 except (ValueError,TypeError): return None
def records(obj):
 if isinstance(obj,dict):
  if isinstance(obj.get('data'),list):return records(obj['data'])
  return [obj]
 if not isinstance(obj,list):return []
 if obj and isinstance(obj[0],list):
  head=obj[0]
  if all(isinstance(z,str) for z in head):return [dict(zip(head,x)) for x in obj[1:] if isinstance(x,list)]
 return [x for x in obj if isinstance(x,dict)]
def extract(obj,keys,filter_fn=None):
 rows=records(obj)
 for x in reversed(rows):
  if filter_fn and not filter_fn(x):continue
  v=next((num(x.get(k)) for k in keys if num(x.get(k)) is not None),None)
  if v is None:continue
  stamp=next((str(x.get(k)) for k in ('time_tag','time','timestamp','observed','date') if x.get(k)),None)
  if stamp and len(stamp)==19 and stamp[10]=='T' and stamp[-1].isdigit(): stamp+='Z'
  return v,stamp
 return None,None
def proton_filter(x):
 energy=str(x.get('energy','')).lower().replace(' ','')
 # NOAA integral-protons energy names: >=10 MeV, >=10, etc.
 if energy and not ('10' in energy and '100' not in energy):return False
 return str(x.get('flux',''))!=''
def collect():
 now=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
 row=dict.fromkeys(FIELDS,'');row['collected_at']=now
 errors=[]
 tasks=[('kp',['Kp','kp','estimated_kp','k_index'],'kp_at',None),('speed',['proton_speed','speed','speed_kms','solar_wind_speed'],'wind_at',None),('mag',['bz_gsm','bz','bz_gse'],'bz_at',None),('proton',['flux'],'protons_at',proton_filter)]
 for name,keys,tfield,filt in tasks:
  try:
   obj=fetch(URLS[name]);value,stamp=extract(obj,keys,filt)
   if value is None:raise ValueError('no valid observation')
   field={'kp':'kp','speed':'wind_kms','mag':'bz_nt','proton':'protons_pfu'}[name]
   row[field]=round(value,3);row[tfield]=stamp or ''
  except Exception as e:errors.append(name+': '+str(e)[:130])
 row['quality']='complete' if not errors else ('partial' if any(row[k]!='' for k in ['kp','wind_kms','bz_nt','protons_pfu']) else 'unavailable')
 row['errors']='; '.join(errors)
 return row
def save(row):
 path=DATA/'history.csv'
 existing=[]
 if path.exists():
  with path.open(newline='',encoding='utf-8') as f:existing=list(csv.DictReader(f))
 # Avoid duplicates within the same 30 min window (workflow retries)
 slot=row['collected_at'][:14]+('00' if int(row['collected_at'][14:16])<30 else '30')
 existing=[r for r in existing if r.get('collected_at','')[:14]+('00' if int(r.get('collected_at','00:00')[14:16] or 0)<30 else '30')!=slot]
 existing.append(row)
 existing.sort(key=lambda x:x['collected_at'])
 with path.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore');w.writeheader();w.writerows(existing)
 (DATA/'latest.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
 (DATA/'history.json').write_text(json.dumps(existing,indent=1),encoding='utf-8')
 return len(existing)
def main():
 row=collect()
 if row['quality']=='unavailable':
  print(json.dumps({'quality':row['quality'],'saved_samples':0,'time':row['collected_at'],'errors':row['errors']}))
  sys.exit(1)
 count=save(row)
 print(json.dumps({'quality':row['quality'],'saved_samples':count,'time':row['collected_at'],'errors':row['errors']}))
if __name__=='__main__':main()
