import ee
import os
import pandas as pd
import datetime
import geemap
# Trigger the authentication flow.
ee.Authenticate()

# Initialize the library.
ee.Initialize()

class polyEE(object):
    def __init__(self,gdf,product,band):
        self.gdf=gdf
        self.product=product
        self.band=band
        self.idate='1991-01-01'
        self.fdate='2021-12-01'

    def addDate(image):
        img_date = ee.Date(image.date())
        img_date = ee.Number.parse(img_date.format('YYYYMMdd'))
        return image.addBands(ee.Image(img_date).rename('date').toInt())

    def gdf2FeatureCollection(self):
        features = []
        for i in range(self.gdf.shape[0]):
            geom = self.gdf.iloc[i:i+1,:] 
            
            jsonDict = json.loads(geom.to_json())
            x=np.array([x[0] for x in jsonDict['features'][0]['geometry']['coordinates'][0]])
            y=np.array([x[1] for x in jsonDict['features'][0]['geometry']['coordinates'][0]])
            cords = np.dstack((x[:],y[:])).tolist()
            g=ee.Geometry.Polygon(cords).bounds()
            feature = ee.Feature(g,{'name':self.gdf.loc[i,'FID']})
            features.append(feature)
        return ee.FeatureCollection(features)

    def rasterExtraction(image):
        feature = image.sampleRegions(**{'collection':ee_fc,'scale':scale})
        return feature
    
    def dl(self):
        dset=ee.ImageCollection(self.product).filterDate(self.idate,
                                                self.fdate).map(self.addDate)
        ee_fc=self.gdf2FeatureCollection()    
        res=dset.filterBounds(ee_fc).select(self.band).map(self.addDate)\
    .map(self.rasterExtraction).flatten()
        column_df=['name']
        column_df.extend([self.band,'date'])
        nested_list = res.reduceColumns(ee.Reducer.toList(len(column_df)),
                                            column_df).values().get(0)
        data = nested_list.getInfo()
        df = pd.DataFrame(data, columns=column_df)
        df.index=pd.to_datetime(df['date'],format="%Y%m%d")
        df=df[[x for x in df.columns if x!='date']]
        df_pivot=pd.pivot_table(df,values=self.band,index=df.index,
                                columns=df['name'])
        return df

def main():
    