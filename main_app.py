from genericpath import exists
import streamlit as st
import pandas as pd
import time

st.title('Stock/Inventory Discrepancy')

with st.sidebar:
    uploaded_files = st.file_uploader('CHOOSE EXPECTED AND COUNTED FILES:', type='csv', accept_multiple_files=True, help='Make sure that both files contains the words "expected" and "counted" in filenames.')

if len(uploaded_files) == 2:
    for file in uploaded_files:
        if 'EXPECTED' in file.name.upper():
            df_expected = pd.read_csv(file.name, encoding='latin-1', dtype=str)
        if 'COUNTED' in file.name.upper():
            df_counted = pd.read_csv(file.name, encoding='latin-1', dtype=str)

    # Expected data, remove duplicates.
    df_expected['Retail_Product_SKU'].count()
    df_expected['Retail_Product_SKU'].nunique()

    # Preparing SOH data to be merged.
    subset_columns = [
        'Retail_Product_Color',
        'Retail_Product_Level1Name',
        'Retail_Product_Level2Name',
        'Retail_Product_Level3Name',
        'Retail_Product_Level4Name',
        'Retail_Product_Level5Name',
        'Retail_Product_Name',
        'Retail_Product_SKU',
        'Retail_Product_Style',
        'serial',
        'Retail_SOHDate',
        'Retail_SOHQTY'
    ]

    df_soh = df_expected[subset_columns]

    df_soh = df_soh.dropna(subset=['Retail_Product_SKU'])

    # Counted data, remove duplicates.
    df_counted['RFID'].count()
    df_counted['RFID'].nunique()

    df_removed_dup = df_counted.drop_duplicates(subset=['RFID'])
    df_removed_dup['RFID'].count()

    # Preparing Inventory CycleCount data to be merged.
    subset_columns_inv_cycle = [
        'Retail_Product_SKU',
        'Retail_Product_Name',
        'Retail_Product_Level1Name',
        'RFID'   
    ]

    # dropping Retail_Product_SKU = NaN
    df_inv_cycle = df_removed_dup[subset_columns_inv_cycle].dropna(subset=['Retail_Product_SKU'])
    df_inv_cycle_agg = df_inv_cycle.groupby(['Retail_Product_SKU', 'Retail_Product_Name', 'Retail_Product_Level1Name']).agg(Inv_Cycle_SOHQTY=('RFID', 'count'))
    df_inv_cycle_agg.reset_index()

    # Merging two datasets
    df_merged = pd.merge(df_soh, df_inv_cycle_agg, how='outer', on=['Retail_Product_SKU', 'Retail_Product_Name', 'Retail_Product_Level1Name'], indicator=True)

    df_merged[['Retail_SOHQTY', 'Inv_Cycle_SOHQTY']] = df_merged[['Retail_SOHQTY', 'Inv_Cycle_SOHQTY']].fillna(0)

    df_merged['Inv_Cycle_SOHQTY'] = df_merged['Inv_Cycle_SOHQTY'].astype('int')
    df_merged['Retail_SOHQTY'] = df_merged['Retail_SOHQTY'].astype('int')

    df_merged['Diff'] = df_merged.apply(lambda row: row.Retail_SOHQTY - row.Inv_Cycle_SOHQTY, axis=1).abs()

    def match_qty(a, b):
        if a == b:
            return 1
        else:
            return 0

    df_merged['Match'] = df_merged.apply(lambda row: match_qty(row.Retail_SOHQTY, row.Inv_Cycle_SOHQTY), axis=1)

    def unders_qty(a, b):
        if a > b:
            return a - b
        else:
            return 0

    df_merged['Unders'] = df_merged.apply(lambda row: unders_qty(row.Retail_SOHQTY, row.Inv_Cycle_SOHQTY), axis=1)

    def overs_qty(a, b):
        if b > a:
            return b - a
        else:
            return 0

    df_merged['Overs'] = df_merged.apply(lambda row: overs_qty(row.Retail_SOHQTY, row.Inv_Cycle_SOHQTY), axis=1)

    # KPI's
    col1, col2, col3, col4, col5 = st.columns(5)

    # Stock On Hand Only
    kpi_soh = round(df_merged.loc[df_merged['_merge'] == 'left_only']['Retail_Product_SKU'].count()*100/df_merged['_merge'].count(), 1)
    col1.metric('Stock On Hand Only', str(kpi_soh)+'%')

    # Inventory Workflow Only
    kpi_iwf = round(df_merged.loc[df_merged['_merge'] == 'right_only']['Retail_Product_SKU'].count()*100/df_merged['_merge'].count(), 1)
    col2.metric('Inv. Workflow Only', str(kpi_iwf)+'%')

    # Both
    kpi_both = round(df_merged.loc[df_merged['_merge'] == 'both']['Retail_Product_SKU'].count()*100/df_merged['_merge'].count(), 1)
    col3.metric('Both', str(kpi_both)+'%')

    # Match
    kpi_match = round(df_merged['Match'].sum()*100/df_merged['Match'].count(), 1)
    col4.metric('Match', str(kpi_match)+'%')

    # Both and Match
    kpi_both_match = round(df_merged.loc[(df_merged['_merge'] == 'both') & (df_merged['Match'] == 1)]['Retail_Product_SKU'].count()*100/df_merged['_merge'].count(), 1)
    col5.metric('Both & Match', str(kpi_both_match)+'%')

    # Detailed Data
    @st.cache
    def export_df_csv(df):
        return df.to_csv().encode('utf-8')
    
    st.dataframe(df_merged)
    csv = export_df_csv(df_merged)

    timestr = time.strftime('%Y%m%d-%H%M%S')

    st.download_button(
        label='Download data as CSV',
        data=csv,
        file_name='discrepancy_'+timestr+'.csv',
        mime='text/csv'
    )

else:
    st.warning('Some CSV file is missing, please review it.')
