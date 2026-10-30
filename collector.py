#!/usr/bin/env python3
"""Parka propagation history/backfill. Python standard library only.

Historical window starts 2026-10-17 00:00 UTC. Blank = no verified observation.
A GitHub run backfills as much as published sources allow, never extrapolates.
"""
import argparse
import bisect
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=True)
UTC = timezone.utc
START = datetime(2026, 10, 17, tzinfo=UTC)
STEP = timedelta(minutes=30)
SWPC = 'https://services.swpc.noaa.gov'
GFZ = 'https://kp.gfz.de/app/json/'
FIELDS = ['collected_at','kp','kp_at','wind_kms','wind_at','bz_nt','bz_at',
          'protons_pfu','protons_at','quality','errors']
SOURCES = {
 'kp_swpc': SWPC+'/products/noaa-planetary-k-index.json',
 'wind': SWPC+'/json/rtsw/rtsw_wind_1m.json',
 'mag': SWPC+'/json/rtsw/rtsw_mag_1m.json',
 'proton': SWPC+'/json/goes/primary/integral-protons-7-day.json',
 'kp_gfz': GFZ,
}

def iso(t):
 return t.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

def parse(t):
 if isinstance(t,(int,float)):return datetime.fromtimestamp(t,UTC)
 if not t:return None
 try:return datetime.fromisoformat(str(t).strip().replace(' ','T').replace('Z','+00:00')).replace(tzinfo=UTC) if datetime.fromisoformat(str(t).strip().replace(' ','T').replace('Z','+00:00')).tzinfo is None else datetime.fromisoformat(str(t).strip().replace(' ','T').replace('Z','+00:00')).astimezone(UTC)
 except (ValueError,OverflowError):return None

def num(v):
 try:
  val=float(v)
  return val if -1e7 < val < 1e7 and val==val else None
 except (TypeError,ValueError):return None

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'ParkaMWNavigator/2.0 scientific historical monitoring','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=35) as resp:return json.load(resp)

def records(obj):
 if isinstance(obj,dict):
  for key in ['data','observations','records']:
   if isinstance(obj.get(key),list):return records(obj[key])
  return [obj]
 if not isinstance(obj,list):return []
 if obj and isinstance(obj[0],list) and all(isinstance(v,str) for v in obj[0]):
  return [dict(zip(obj[0],r)) for r in obj[1:] if isinstance(r,list)]
 return [r for r in obj if isinstance(r,dict)]

def observed(r):
 for key in ('time_tag','time','timestamp','observed','date','timeTag'):
  if r.get(key):return parse(r[key])
 return None

def series(obj,keys,filter_fn=None):
 out=[]
 for r in records(obj):
  if filter_fn and not filter_fn(r):continue
  stamp=observed(r)
  if stamp is None:continue
  val=next((num(r.get(k)) for k in keys if num(r.get(k)) is not None),None)
  if val is None:continue
  out.append((stamp,val))
 return sorted(set(out))

def proton_filter(r):
 energy=str(r.get('energy','')).lower().replace(' ','').replace('≥','>=')
 if energy:
  # Channel labelled >=10 MeV, not >=100 MeV or 10-30 MeV differential.
  return energy in ('>=10mev','>=10','>10mev','>10','10mev','10','p10')
 return str(r.get('channel','')).lower() in ('p10','>=10mev')

def kp_from_gfz(obj):
 # GFZ web API provides parallel arrays: datetime, Kp, status.
 if isinstance(obj,dict):
  ts=obj.get('datetime') or obj.get('time') or []
  vals=obj.get('Kp') or obj.get('kp') or []
  if isinstance(ts,list) and isinstance(vals,list):
   return sorted((t,v) for stamp,val in zip(ts,vals)
                 if (t:=parse(stamp)) is not None and (v:=num(val)) is not None)
 return series(obj,['Kp','kp','value'])

def nearest(series_data,stamp,max_age):
 """Only use observation at or before slot and no older than max_age."""
 if not series_data:return (None,None)
 i=bisect.bisect_right(series_data,(stamp,float('inf')))-1
 if i<0:return (None,None)
 t,v=series_data[i]
 if stamp-t > max_age:return (None,None)
 return (v,t)

def load_existing():
 path=DATA/'history.csv'
 if not path.exists():return {}
 result={}
 with path.open(newline='',encoding='utf-8') as fp:
  for r in csv.DictReader(fp):
   dt=parse(r.get('collected_at'))
   if dt is None or dt < START:continue
   dt=dt.replace(minute=0 if dt.minute<30 else 30,second=0,microsecond=0)
   result[iso(dt)]=r
 return result

def prefer(old,new,key,datekey):
 """Prefer a non-empty value, and a more timely observation when both exist."""
 nv=num(new.get(key));ov=num(old.get(key))
 if nv is None:return
 if ov is None:
  old[key]=round(nv,3);old[datekey]=new.get(datekey,'');return
 t_old=parse(old.get(datekey));t_new=parse(new.get(datekey))
 slot=parse(old.get('collected_at'))
 if t_new and (not t_old or abs((slot-t_new).total_seconds())<abs((slot-t_old).total_seconds())):
  old[key]=round(nv,3);old[datekey]=new.get(datekey,'')

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--start',default='2026-10-17',help='Historical start, cannot predate 2026-10-17')
 ap.add_argument('--no-network',action='store_true',help='Test-only: merge existing records without network')
 args=ap.parse_args()
 requested=parse(args.start)
 if requested is None:ap.error('invalid --start date')
 start=max(START,requested)
 now=datetime.now(UTC)
 end=now.replace(minute=0 if now.minute<30 else 30,second=0,microsecond=0)
 old=load_existing(); fetched={}; failures=[]
 def grab(name,url):
  if args.no_network:return None
  try:
   obj=fetch(url)
   print('Fetched',name,flush=True)
   return obj
  except Exception as exc:
   failures.append(name+': '+str(exc)[:115]);print('WARNING',failures[-1],flush=True);return None

 gfz_url=GFZ+'?'+urllib.parse.urlencode({'start':iso(start),'end':iso(end),'index':'Kp'})
 gfz=grab('GFZ historical Kp',gfz_url)
 kp=kp_from_gfz(gfz) if gfz is not None else []
 swpc_kp=grab('SWPC recent Kp',SOURCES['kp_swpc'])
 if swpc_kp is not None:
  swpc_vals=series(swpc_kp,['Kp','kp','estimated_kp','k_index'])
  # Historical GFZ preferred when available; SWPC fills any recent GFZ coverage gap.
  available={t for t,_ in kp};kp+= [(t,v) for t,v in swpc_vals if t not in available]
  kp.sort()
 wind=grab('NOAA solar wind 1m',SOURCES['wind']);mag=grab('NOAA IMF 1m',SOURCES['mag'])
 proton=grab('NOAA GOES proton 7day',SOURCES['proton'])
 wind_vals=series(wind,['proton_speed','speed','solar_wind_speed','speed_kms']) if wind is not None else []
 mag_vals=series(mag,['bz_gsm','bz','bz_gse']) if mag is not None else []
 proton_vals=series(proton,['flux'],proton_filter) if proton is not None else []
 # Fallback summary endpoints for the latest reading if full solar wind feed changed schema.
 if not wind_vals:
  obj=grab('NOAA wind summary',SWPC+'/products/summary/solar-wind-speed.json')
  if obj is not None:wind_vals=series(obj,['proton_speed','speed','solar_wind_speed','speed_kms'])
 if not mag_vals:
  obj=grab('NOAA magnetic summary',SWPC+'/products/summary/solar-wind-mag-field.json')
  if obj is not None:mag_vals=series(obj,['bz_gsm','bz','bz_gse'])

 vals={'kp':(kp,timedelta(hours=3)), 'wind_kms':(wind_vals,timedelta(minutes=40)),
       'bz_nt':(mag_vals,timedelta(minutes=40)), 'protons_pfu':(proton_vals,timedelta(minutes=40))}
 datekeys={'kp':'kp_at','wind_kms':'wind_at','bz_nt':'bz_at','protons_pfu':'protons_at'}
 # Fill half-hour slots from requested start; earlier existing history is preserved.
 t=start.replace(minute=0 if start.minute<30 else 30,second=0,microsecond=0)
 count=0
 while t<=end:
  key=iso(t)
  row=old.get(key,dict.fromkeys(FIELDS,''));row['collected_at']=key
  for name,(sample,max_age) in vals.items():
   v,stamp=nearest(sample,t,max_age)
   if v is not None:prefer(row,{name:v,datekeys[name]:iso(stamp)},name,datekeys[name])
  present=sum(num(row.get(k)) is not None for k in datekeys)
  row['quality']='complete' if present==4 else ('partial' if present else 'unavailable')
  row['errors']='' if present==4 else 'Missing: '+', '.join(k for k in datekeys if num(row.get(k)) is None)
  old[key]=row;count+=1;t+=STEP
 # Latest must point to newest slot with observed data, not a future/empty row.
 ordered=sorted(old.values(),key=lambda r:r['collected_at'])
 latest=next((r for r in reversed(ordered) if r['quality']!='unavailable'),{})
 with (DATA/'history.csv').open('w',encoding='utf-8',newline='') as fp:
  writer=csv.DictWriter(fp,fieldnames=FIELDS,extrasaction='ignore');writer.writeheader();writer.writerows(ordered)
 (DATA/'history.json').write_text(json.dumps(ordered,separators=(',',':')),encoding='utf-8')
 (DATA/'latest.json').write_text(json.dumps(latest,indent=2),encoding='utf-8')
 summary={'from':iso(start),'to':iso(end),'slots':count,'stored_total':len(ordered),'complete':sum(r['quality']=='complete' for r in ordered),'partial':sum(r['quality']=='partial' for r in ordered),'unavailable':sum(r['quality']=='unavailable' for r in ordered),'latest':latest.get('collected_at'),'source_errors':failures}
 (DATA/'collection_status.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 print(json.dumps(summary,indent=2))
 if not any(r['quality']!='unavailable' for r in ordered):sys.exit('No actual observations were available; inspect NOAA/GFZ endpoints')

if __name__=='__main__':main()
