import ee
import os
import pandas as pd
import datetime
import geemap
import geopandas as gpd
import json
import numpy as np

service_account = 'srmearthenginelogin@srmlogin.iam.gserviceaccount.com'
folder_json = os.path.join('.','auth',
                           'srmlogin-175106b08655.json')
credentials = ee.ServiceAccountCredentials(service_account, folder_json)
ee.Initialize(credentials)

class polyEE(object):
    def __init__(self,name,gdf,product,band,scale):
        self.name=name
        self.gdf=gdf.to_crs(epsg=4326)
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
            geo2=geo.explode()
            geo3=gpd.GeoDataFrame([],geometry=geo2.geometry,crs='4326')
            geo3['area']=''
            geo3['area']=geo3.to_crs(epsg='32719').apply(lambda x: x['geometry'].area,
                                                         axis=1)
            geo3=geo3.sort_values('area',ascending=False)
            geo3=geo3.iloc[0].drop('area')
            geo3=gpd.GeoDataFrame(pd.DataFrame(geo3).T)
            return geo3.buffer(0)
        else:
            return geo
        
    def gdf2FeatureCollection(self,gs):
        features = []
        for i in range(gs.shape[0]):
            geom = gs.iloc[i:i+1,:] 
            geom=self.fixMultipoly(geom)
            print(geom.set_crs(epsg='4326').to_crs(epsg='32719').area.apply(lambda x: f'{x:.20f}'))
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
    
    def rasterExtracion2(self,image):
        mean = image.reduceRegion(reducer=ee.Reducer.mean(),
            geometry=self.ee_fc.geometry(),
            scale=self.scale,
            crs='EPSG:32719')
        return image.set('date', image.date().format()).set(mean)
    
    def filterQA(self,image):
        qa = image.select('NDSI_Snow_Cover_Basic_QA')
        goodQA = qa.eq(0)
        return image.updateMask(goodQA)
    
    def filterCouds(self,image):
        clouds=image.select('NDSI_Snow_Cover_Class')
        noClouds = clouds.neq(250)
        return image.updateMask(noClouds)

    def filterMax(self,image):
        filterMask=image.lt(100)
        return image.updateMask(filterMask)
    
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

    def partitionDates(self,periods=2):

        datei=self.getDate()[0].format('YYYYMMdd').getInfo()
        datef=self.getDate()[1].format('YYYYMMdd').getInfo()
        return list(pd.date_range(start=datei,end=datef,periods=periods))

    def ImagesToDataFrame(self,images,band):
        column_df=['date',band]
        nested_list = images.reduceColumns(ee.Reducer.toList(len(column_df)),
                                            column_df).values().get(0)
        data = nested_list.getInfo()
        df = pd.DataFrame(data, columns=column_df)
        df.index=pd.to_datetime(df['date'],format="%Y-%m-%d")
        df=df[[x for x in df.columns if x!='date']]
        return df
    
    def QA(self,df_,dfQA_):
        df_=df_[:]
        dfQA_=dfQA_.loc[df_.index]
        treshold=dfQA_.loc[df_.index].quantile(.85)[0]
        df_=df_[dfQA_[dfQA_.columns[0]]<=treshold]
        return df_
    
    def spatialFill(self,image):
        #function to fill spatial gaps in an image using the nearest pixels in
        #google earth engine
        temp=ee.Image().clip(self.ee_fc.geometry())
        unmasked=image.unmask(temp)
        filled=image.focal_mean(1001,'square','meters', 9)
        join=filled.copyProperties(image, ['system:time_start'])
        return join
 
    def dl(self):
        periods=10
        listPeriods=self.partitionDates(periods)

        idx=pd.date_range(listPeriods[0],listPeriods[-1])
        dfRet=pd.DataFrame(index=idx,columns=list(self.gdf.index))
        dset=ee.ImageCollection(self.product)
        for ind,date in enumerate(listPeriods[:-1]):
            lista=[]
            for index in self.gdf.index:
                gdfTemp=self.geoSeries2GeoDataFrame(self.gdf.loc[index])
                gdfTemp=self.num2str(gdfTemp)
                # self.ee_fc=self.gdf2FeatureCollection(gdfTemp)    
                self.ee_fc=geemap.geopandas_to_ee(gdfTemp.set_crs(epsg='4326'))
                if 'NDSI_Snow_Cover' in self.band:
                    dset=dset.map(self.filterQA).map(self.filterCouds)
                    resQA=dset.filterBounds(self.ee_fc).select('NDSI_Snow_Cover_Basic_QA').filterDate(ee.Date(date),
ee.Date(listPeriods[ind+1])).map(self.rasterExtracion2)
                    dfQA=self.ImagesToDataFrame(resQA,
                                                'NDSI_Snow_Cover_Basic_QA')
                res=dset.filterBounds(self.ee_fc).select(self.band)
                resDates=res.filterDate(ee.Date(date),
ee.Date(listPeriods[ind+1])).map(self.spatialFill).map(self.rasterExtracion2).map(self.filterMax)
                df=self.ImagesToDataFrame(resDates,self.band)
                try:
                    dfQCED=self.QA(df,dfQA)
                except:
                    pass
                lista.append(dfQCED)
            lista2=self.fixColumns(lista)
            dfDate=pd.concat(lista2, axis=1, ignore_index=False)
            dfRet.loc[dfDate.index,:]=dfDate.values
        
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
        df=df.fillna(method='bfill').fillna(method='ffill')
        # df=df[df.columns].fillna(df[df.columns].rolling(7,center=True,
        #                                              min_periods=1).mean())
        return df
    
def main3():
    path=r'G:\OneDrive - ciren.cl\2022_ANID_sequia\Proyecto\SIG\Cuencas\subcNClimari.shp'
    path=r'G:\OneDrive - ciren.cl\Ficha_16_Coquimbo\02_SIG\02_Aguas sup\04_Regional\cuencas_cabecera\Rio Hurtado En San Agustin\bands4calhypso_fix.shp'
    gdfCuenca=gpd.read_file(path)
    # gdfCuenca=gpd.GeoDataFrame(pd.DataFrame(gdf.iloc[0]).T)
    cuenca=polyEE(gdfCuenca,'MODIS/006/MOD10A1','NDSI_Snow_Cover',500)
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

    name='Hurtado_San_Agustin'
    pth=os.path.join('..',name,'glacierBands.shp')
    pth=r'G:\OneDrive - ciren.cl\Ficha_16_Coquimbo\02_SIG\02_Aguas sup\04_Regional\cuencas_cabecera\Rio Hurtado En San Agustin\bands4calhypso_fix.shp'
    gdfCuenca=gpd.read_file(pth)
    # bf=polyEE(gdfCuenca,name,'NASA/FLDAS/NOAH01/C/GL/M/V001','Qsb_tavg',11132)
    terra=polyEE(name,gdfCuenca,'MODIS/006/MYD10A1','NDSI_Snow_Cover',500)
    aqua=polyEE(name,gdfCuenca,'MODIS/006/MOD10A1','NDSI_Snow_Cover',500)
    
    # bajar terra
    dfTerra=terra.fillColumns(terra.dl())

    # bajar aqua
    dfAqua=aqua.fillColumns(aqua.dl())
    
    # resultados
    dfOut=dfTerra.combine_first(dfAqua)
    # dfOut.columns=[x-1 for x in list(gdfCuenca.index)]
    
    # rellenar el df
    dfAll=pd.DataFrame(np.nan,index=pd.date_range('2000-01-01',
                            dfOut.index.max(),freq='D'),
                            columns=dfOut.columns)
    dfAll.loc[dfOut.index,dfOut.columns]=dfOut.values

    dfAll=terra.fillColumns(dfAll)
    dfOut=dfAll.fillna(0)
    dfOut=dfOut/100.

    dfOut.to_csv(os.path.join('..',name,'glacierCover.csv' ))

if __name__=='__main__':
    main()