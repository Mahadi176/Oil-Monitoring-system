import pandas as pd
from database import db_connection
from database.schema import init_db
from database.queries import create_user,authenticate,organisations,import_records,load_records

def test_auth_and_duplicate_persistence(tmp_path,monkeypatch):
    db=tmp_path/'test.db'; monkeypatch.setattr(db_connection,'DB_PATH',db)
    init_db(); ok,_=create_user('demo','12345'); assert ok
    uid=authenticate('demo','12345'); assert uid
    df=pd.DataFrame([{'Date':pd.Timestamp('2026-11-01'),'TotalCost':1000,'Litres':10,'Oil Rate':100,'Oil Cost':500,'Oil Cost %':50,'Employee Cost':200,'Transportation Cost':200,'Other Costs':100}])
    r=import_records(uid,'Company A',df,'a.xlsx'); assert r=={'imported':1,'skipped':0}
    r=import_records(uid,'Company A',df,'a.xlsx'); assert r=={'imported':0,'skipped':1}
    assert len(load_records(uid))==1 and len(organisations(uid))==1

def test_pin_must_be_five_digits_and_replace_is_explicit(tmp_path,monkeypatch):
    db=tmp_path/'test2.db'; monkeypatch.setattr(db_connection,'DB_PATH',db)
    init_db()
    ok,_=create_user('another','1234'); assert not ok
    ok,_=create_user('another','12345'); assert ok
    uid=authenticate('another','12345'); assert uid
    df=pd.DataFrame([{'Date':pd.Timestamp('2026-11-01'),'TotalCost':1000,'Litres':10,'Oil Rate':100,'Oil Cost':500,'Oil Cost %':50,'Employee Cost':200,'Transportation Cost':200,'Other Costs':100}])
    import_records(uid,'Org',df,'org.xlsx')
    updated=df.copy(); updated.loc[0,'TotalCost']=1200
    skipped=import_records(uid,'Org',updated,'org.xlsx',replace_existing=False)
    assert skipped['skipped']==1 and load_records(uid).iloc[0]['total_cost']==1000
    replaced=import_records(uid,'Org',updated,'org.xlsx',replace_existing=True)
    assert replaced['imported']==1 and load_records(uid).iloc[0]['total_cost']==1200
