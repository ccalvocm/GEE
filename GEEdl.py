import ee
import os
import pandas as pd
import datetime
import geemap
import geopandas as gpd
import json
import numpy as np

service_account = 'srmearthenginelogin@srmlogin.iam.gserviceaccount.com'
folder_json = os.path.join('.','interfaz_descarga_GEE',
                           'srmlogin-175106b08655.json')
credentials = ee.ServiceAccountCredentials(service_account, folder_json)
ee.Initialize(credentials)

class polyEE(object):
    def __init__(self,gdf,name,product,band,scale):
        self.gdf=gdf.to_crs(epsg=4326)
        self.name=name
        self.product=product
        self.ee_fc=None
        self.band=band
        self.idate=None
        self.fdate=None
        self.scale=scale

    def addDate(self,image):
        img_date = ee.Date(image.date())
        img_date = ee.Number.parse(img_date.format('YYYYMMdd'))
        return image.addBands(ee.Image(img_date).rename('date').toInt())
    
    def fixMultipoly(self,geo):
        if 'MultiPolygon' in str(type(geo.geometry.iloc[0])):
            geo2=geo.explode().iloc[1:]
            geo3=gpd.GeoDataFrame([],geometry=geo2.geometry,crs='4326')
            geo3['area']=''
            geo3['area']=geo3.to_crs(epsg='32719').apply(lambda x: x['geometry'].area,
                                                         axis=1)
            geo3=geo3.sort_values('area',ascending=False)
            geo3=geo3.iloc[0].drop('area')
            geo3=gpd.GeoDataFrame(pd.DataFrame(geo3).T)
            return geo3.simplify(.001).buffer(0.001)
        else:
            return geo
        
    def gdf2FeatureCollection(self,gs):
        features = []
        for i in range(gs.shape[0]):
            geom = gs.iloc[i:i+1,:] 
            geom=self.fixMultipoly(geom)
            jsonDict = json.loads(geom.to_json())
            x=np.array([x[0] for x in jsonDict['features'][0]['geometry']['coordinates'][0]])
            y=np.array([x[1] for x in jsonDict['features'][0]['geometry']['coordinates'][0]])
            cords = np.dstack((x[:],y[:])).tolist()
            # g=ee.Geometry.Polygon(cords).bounds()
            g=ee.Geometry.Polygon(cords)
            # feature = ee.Feature(g,{'name':self.gdf.loc[i,col].astype(str)})
            feature = ee.Feature(g)
            features.append(feature)
        return ee.FeatureCollection(features)

    def rasterExtraction(self,image):
        feature = image.sampleRegions(**{'collection':self.ee_fc,
                                         'scale':self.scale})
        return feature
    
    def geoSeries2GeoDataFrame(self,gs):
        temp=gpd.GeoDataFrame(pd.DataFrame(gs).T)
        if 'geometry' in temp.columns:
            return temp
        else:
            return gpd.GeoDataFrame(pd.DataFrame(gs)) 

    def num2str(self,gs):
        col=[x for x in gs.columns if x!='geometry'][0]
        gs[col]=gs[col].astype(str)
        return gs	

    def dl(self):
        self.idate=self.getDate()[0]
        self.fdate=self.getDate()[1]
        dset=ee.ImageCollection(self.product).filterDate(self.idate,
                                                self.fdate).map(self.addDate)
        lista=[]
        for index in self.gdf.index:
            print(index)
            gdfTemp=self.geoSeries2GeoDataFrame(self.gdf.loc[index])
            gdfTemp=self.num2str(gdfTemp)
            self.ee_fc=self.gdf2FeatureCollection(gdfTemp)    
            res=dset.filterBounds(self.ee_fc).select(self.band).map(self.addDate)\
        .map(self.rasterExtraction).flatten()
            # column_df=['name']
            # column_df.extend([self.band,'date'])
            column_df=[self.band,'date']
            nested_list = res.reduceColumns(ee.Reducer.toList(len(column_df)),
                                                column_df).values().get(0)
            data = nested_list.getInfo()
            df = pd.DataFrame(data, columns=column_df)
            df.index=pd.to_datetime(df['date'],format="%Y%m%d")
            df=df[[x for x in df.columns if x!='date']]
            # df_pivot=pd.pivot_table(df,values=self.band,index=df.index,
            #                         columns=df[self.band])
            lista.append(df)
        lista2=self.fixColumns(lista)
        dfRet=pd.concat(lista2, axis=1, ignore_index=False)
        return dfRet
    
    def fixColumns(self,lista):
        lista2=[]
        for ind,df in enumerate(lista):
            df.columns=[str(ind)]
            df = df.loc[~df.index.duplicated(keep='first')]
            lista2.append(df)
        return lista2

    def getDate(self):
        collection = ee.ImageCollection(self.product)
        date_range = collection.reduceColumns(ee.Reducer.minMax(),
                                          ['system:time_start'])
        jsondate1 = ee.Date(date_range.get('min'))
        jsondate2 = ee.Date(date_range.get('max'))
        return (jsondate1,jsondate2)
    
    def fillColumns(self,df):
        df=df[df.columns].fillna(df[df.columns].rolling(60,center=False,
                                                     min_periods=1).mean())
        return df

    
def main():
    path=r'G:\OneDrive - ciren.cl\2022_ANID_sequia\Proyecto\SIG\Cuencas\subcNClimari.shp'
    gdfCuenca=gpd.read_file(path)
    # gdfCuenca=gpd.GeoDataFrame(pd.DataFrame(gdf.iloc[0]).T)
    cuenca=polyEE(gdfCuenca,'MODIS/006/MOD10A1','NDSI_Snow_Cover',500,'2000-02-24','2023-02-17')
    df=cuenca.dl()

    product='IDAHO_EPSCOR/TERRACLIMATE'
    band='ro'
    scale=11132
    cuenca=polyEE(gdfCuenca,product,band,scale)
    df=cuenca.dl()
    df.plot()
    dfOut=df.pivot_table(index='date',columns='name',
                values='ro').mul(gdfCuenca.to_crs(epsg='32719').area.values,
                                 1)/(86400000)
    dfOut=dfOut.divide(dfOut.index.days_in_month,axis=0)
    dfOut.to_csv(r'G:\OneDrive - ciren.cl\2022_ANID_sequia\Proyecto\3_Objetivo3\Modelos\insumosWEAP\qPunitaquiIngenioPonio.csv')

if __name__=='__main__':
    pth=r'G:\OneDrive - ciren.cl\Ficha_16_Coquimbo\02_SIG\02_Aguas sup\04_Regional\cuencas_cabecera\Rio Hurtado En San Agustin\bands4calhypso_fix.shp'
    name='Hurtado_San_Agustin'
    pth=os.path.join('..',name,'glacierBands.shp')
    pth=r'G:\OneDrive - ciren.cl\Ficha_16_Coquimbo\02_SIG\02_Aguas sup\04_Regional\cuencas_cabecera\Rio Hurtado En San Agustin\basin4calhypso.shp'
    gdfCuenca=gpd.read_file(pth).set_index('FID')
    bf=polyEE(gdfCuenca,name,'NASA/FLDAS/NOAH01/C/GL/M/V001','Qsb_tavg',11132)
    terra=polyEE(gdfCuenca,name,'MODIS/006/MYD10A1','NDSI_Snow_Cover',500)
    aqua=polyEE(gdfCuenca,name,'MODIS/006/MOD10A1','NDSI_Snow_Cover',500)
    
    # bajar terra
    dfTerra=terra.fillColumns(terra.dl())

    # bajar aqua
    dfAqua=aqua.fillColumns(aqua.dl())
    
    # resultados
    dfOut=dfTerra.combine_first(dfAqua)
    dfOut.columns=[x-1 for x in list(gdfCuenca.index)]
    
    # rellenar el df
    dfAll=pd.DataFrame(np.nan,index=pd.date_range('2000-01-01',
                            dfOut.index.max(),freq='D'),
                            columns=dfOut.columns)
    dfAllGlacier=dfAll.copy()
    dfAll.loc[dfOut.index,dfOut.columns]=dfOut.values

    dfAll=terra.fillColumns(dfAll)
    dfOut=dfAll.fillna(100)
    dfOut=dfOut/100.

    dfOut.to_csv(os.path.join('..',name,'glacierCover.csv' ))
    # main()