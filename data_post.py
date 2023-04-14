import pandas as pd
import numpy as np
import pgeocode
nomi = pgeocode.Nominatim('fr')
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from pivottablejs import pivot_ui
from PIL import Image

st.set_page_config(
    page_title="Famileat - Dashboard livraisons",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'mailto:pacdev.ei@gmail.com',
        'Report a bug': "mailto:pacdev.ei@gmail.com",
        'About': """Dashboard pour suivre les statistiques de livraisons de Famileat https://www.famileat.fr.
        Développée par pacdev https://pacdev.pythonanywhere.com."""
    }
)


image = Image.open('./logo.png')

st.markdown("# Famileat-dashboard")
st.image(image, width=200)

# dict for corresp on statut and name in df column name
CORRESP_STATUT = {
    "Livré": "nbre_colis_livres",
    "Non Livré": "nbre_colis_non_livres",
    "Retard": "nbre_colis_livres_Retard",
    "Erreur colisage": "nbre_colis_livres_Erreur colisage"
}

def clean_data(df_raw):
    
    df = df_raw.copy()
    df = df.drop_duplicates()
    
    ignored_lines = df['Code postal destinataire'].isna().sum()
    if ignored_lines >= 1:
        st.warning(f"{ignored_lines} lignes ignorée(s) car il manque le code postal de la destination")
    # ensure 5 digit in code postale
    df.dropna(subset=["Code postal destinataire"], inplace=True)
    df["Code postal destinataire"] = df["Code postal destinataire"].astype('str').apply(lambda elem:elem.zfill(5))
    
    # low case for erreur colissage and delay
    df["Erreur de colissage/Manque"] = df["Erreur de colissage/Manque"].apply(lambda elem:elem.lower())
    
    df["Date livraison"] = pd.to_datetime(df["Date de livraison"], format="%Y-%m-%d", errors='coerce')
    df["Date arrivée client"] = pd.to_datetime(df["Date arrivée client"], format="%Y-%m-%d", errors='coerce')
    df["Mois livraison"] = df["Date livraison"].dt.month_name()
    
    df["Remis le"] = pd.to_datetime(df["Date de ramasse"], format="%Y-%m-%d", errors='coerce')
    df["delta_jour"] = df["Date livraison"].dt.date - df["Remis le"].dt.date # keep only date witout time to calculate the delta day
    df["delta_jour_residence"] = df["Date arrivée client"].dt.date - df["Date livraison"].dt.date
    df["Retard residence"] = np.where(df["delta_jour_residence"].dt.days > 1, "oui", "non")
    # replace if any or create
    df["Retard"] = np.where(df["delta_jour"].dt.days > 1, "oui", "non")
    
    
    df.drop(columns=["No de ligne",], inplace=True)
    
    return df
    
def delivered_by_city(df, statut_livraison, livraison_condition=None):        
    # find the number of colis per city DELIVERED or UNDELIVERED
    
    if statut_livraison == "Livré":
        df_delivered = df[df["Status"] == "Livré"]
        if livraison_condition == "Retard":
            df_delivered = df_delivered[df_delivered["Retard"] == "oui"] # show only delay for delivered colis
        elif livraison_condition == "Erreur colisage":
            df_delivered = df_delivered[df_delivered["Erreur de colissage/Manque"] == "oui"]
    else:
        df_delivered = df[df["Status"] != "Livré"]
    
    series_delivered_count = df_delivered.groupby("Code postal destinataire")["Status"].count()
    df_delivered_count = nomi.query_postal_code(series_delivered_count.index.values)
    
    if livraison_condition:
        df_delivered_count[f"{CORRESP_STATUT[statut_livraison]}_{livraison_condition}"] = series_delivered_count.values
    else:    
        df_delivered_count[CORRESP_STATUT[statut_livraison]] = series_delivered_count.values
    
    # ensure that ville destinataire is used
    df_city_code = df[["Code postal destinataire", "Ville destinataire"]].drop_duplicates()
    df_city_code["postal_code"] = df_city_code["Code postal destinataire"]
    
    # delivered
    df_delivered_count = df_delivered_count.merge(df_city_code, how="left", on="postal_code")
    
    return df_delivered_count

def delivered_by_solution(df):
    
    delivered_by_solution = df.groupby("Transporteur")["Transporteur"].count()
    delivered_by_solution.columns = ["Nombre de livraison par solution"]
    
    return delivered_by_solution

def map_delivered_by_city(df, statut_livraison, livraison_condition=None):
    
    if livraison_condition:
        column_name = f"{CORRESP_STATUT[statut_livraison]}_{livraison_condition}"
    else:    
        column_name = CORRESP_STATUT[statut_livraison] 
    
    fig = px.scatter_mapbox(
    data_frame=df,
    lat=df['latitude'], lon=df['longitude'],
    mapbox_style = 'open-street-map',
    size=column_name,
    hover_name='Ville destinataire',
    zoom=4,
    color=column_name,
    color_continuous_scale=px.colors.sequential.Bluered,
    height=700,
    )
    
    
    return fig


if __name__ == "__main__":
        
    # extract the data from the excel file
    st.markdown("## Fichier d'entrée")
    col1, col2 = st.columns(2)
    
    with col1:
        raw_data_file = st.file_uploader("Envoyer votre fichier")
    
    if raw_data_file is not None:
        
        # choose the sheetname to be used
        sheet_names = pd.ExcelFile(raw_data_file).sheet_names
        sheet_name_choices = ["-"]
        for sheet_name in sheet_names:
            sheet_name_choices.append(sheet_name)
        with col2:
            selected_sheet_name = st.selectbox("Choisissez l'onglet que vous voulez traiter",
                                               sheet_name_choices)
        
        if selected_sheet_name != "-":
        
            st.markdown("## Statistiques générales")
            
            df_raw_data = pd.read_excel(raw_data_file, sheet_name=selected_sheet_name,
                                        dtype={'Code postal destinataire': str})
            df = clean_data(df_raw_data)
            
            # pivot table 
            with st.expander("Tableau croisé dynamique interactif"):
                df_pivot = df[["Ville destinataire", "Transporteur", "Résidence", "Retard", "Retard residence", "Erreur de colissage/Manque", "Mois livraison"]].sort_values(by="Mois livraison", ascending=False)
            
                t = pivot_ui(df_pivot, menuLimit=1000)

                with open(t.src) as t:
                    components.html(t.read(), height=1000, scrolling=True)
            
            # first intro dashboard
            with st.container():
                n_comands = df.shape[0]
                n_delivered = df[df["Status"] == "Livré"].shape[0]
                n_undelivered = df[df["Status"] != "Livré"].shape[0]
                n_error_colissage = df[df["Erreur de colissage/Manque"] == "oui"].shape[0]
                n_delay = df[df["Retard"] == "oui"].shape[0]
                
                st.info(f'{n_comands} commandes au total', icon="ℹ️")
                
                col1, col2 = st.columns(2)

                with col1:
                    st.success(f'{n_delivered} commandes livrées avec succés, soit {round(n_delivered/n_comands*100, 1)} %',
                            icon="✅")
                with col2:
                    st.error(f'{n_undelivered} commandes non livrées, soit {round(n_undelivered/n_comands*100, 1)} %',
                            icon="🚨")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.warning(f'{n_delay} livraisons avec retard, soit {round(n_delay/n_delivered*100, 1)} %',
                            icon="⚠️")
                with col2:
                    st.error(f'{n_error_colissage} livraisons avec erreur colissage, soit {round(n_error_colissage/n_delivered*100, 1)} %',
                            icon="🚨")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    n_ville_print = st.slider("Combien de villes voulez vous afficher ?", min_value=2, max_value=10)
                    bar_most_city = px.bar(df.groupby("Ville destinataire")["Ville destinataire"].count().sort_values(ascending=False)[:n_ville_print],
                                        title=f"Les {n_ville_print} villes ayant le plus de commandes")
                    st.plotly_chart(bar_most_city, use_container_width=True)
                
                with col2:
                    n_solution_print = st.slider("Combien de livreurs voulez vous afficher ?", min_value=2, max_value=10)
                    bar_most_solution = px.bar(df.groupby("Transporteur")["Transporteur"].count().sort_values(ascending=False)[:n_solution_print], title=f"Les {n_solution_print} livreurs ayant le plus de commandes")
                    st.plotly_chart(bar_most_solution, use_container_width=True)
                
            # delivered by city container
            with st.container():
                st.markdown("## Répartition géographique des livraisons")
                
                df_delivered_by_city = delivered_by_city(df, "Livré")
                df_undelivered_by_city = delivered_by_city(df, "Non Livré") # undelivered will be everything expect "Livré"
                df_delay_by_city = delivered_by_city(df, "Livré", "Retard") 
                df_error_by_city = delivered_by_city(df, "Livré", "Erreur colisage")
                
                fig_delivered_by_city = map_delivered_by_city(df_delivered_by_city, "Livré")
                fig_undelivered_by_city = map_delivered_by_city(df_undelivered_by_city, "Non Livré")
                fig_delay_by_city = map_delivered_by_city(df_delay_by_city, "Livré", "Retard")
                fig_error_by_city = map_delivered_by_city(df_error_by_city, "Livré", "Erreur colisage")
                
                #do the interactive plot of delivered colis
                
                plot_choice = st.radio(
                    "Sélectionner ce que vous voulez voir apparaître sur la carte",
                    ('Livré', 'Non livré', 'Retard', 'Erreur colisage'), horizontal=True)
                if plot_choice == "Livré":
                    st.plotly_chart(fig_delivered_by_city, use_container_width=True)
                elif plot_choice == "Non livré":
                    st.plotly_chart(fig_undelivered_by_city, use_container_width=True)
                elif plot_choice == "Retard":
                    st.plotly_chart(fig_delay_by_city, use_container_width=True)
                elif plot_choice == "Erreur colisage":
                    st.plotly_chart(fig_error_by_city, use_container_width=True)
            
            # stats by residence
            with st.container():
                st.markdown("## Statistiques par résidence")
                df_residence = df.copy()
                df_residence.replace(to_replace=np.nan, value="particuliers", inplace=True)
                tab1, tab2 = st.tabs(["Pie chart", "Hist."])
                with tab1:
                    pie_by_residence = px.pie(df_residence, names="Résidence", title="% du nombre total de livraisons par résidence")
                    st.plotly_chart(pie_by_residence, use_container_width=True)
                with tab2:
                    hist_by_residence = px.histogram(df_residence, x="Résidence", title="Nombre de livraisons par résidence")
                    st.plotly_chart(hist_by_residence, use_container_width=True)
                
                df_residence_pv_mmv = df.copy()
                df_residence_pv_mmv = df_residence_pv_mmv[df_residence_pv_mmv["Résidence"].isin(["PV", "MMV"])]
                pie_retard_residence = px.histogram(df_residence_pv_mmv, x="Résidence", color="Résidence", pattern_shape="Retard residence" ,title="Retard par résidences PV & MMV")
                
                st.plotly_chart(pie_retard_residence)
                
            # stats by solution
            with st.container():
                
                st.markdown("## Statistiques par livreur")
                df_by_solution = delivered_by_solution(df)
                df_by_solution_delivered = delivered_by_solution(df[df["Status"] == "Livré"])
                df_by_solution_delivered_taux = df_by_solution_delivered/df_by_solution * 100
                
                df_by_solution_delivered_delay = delivered_by_solution(df[(df["Status"] == "Livré") & (df["Retard"] == "oui")])
                df_by_solution_delivered_delay_taux = df_by_solution_delivered_delay/df_by_solution_delivered * 100
                
                df_by_solution_delivered_erreur = delivered_by_solution(df[(df["Status"] == "Livré") & (df["Erreur de colissage/Manque"] == "oui")])
                df_by_solution_delivered_erreur_taux = df_by_solution_delivered_erreur/df_by_solution_delivered * 100
                
                col1, col2 = st.columns(2)
                
                with col1:
                    tab1, tab2 = st.tabs(["Pie chart", "Hist."])
                    with tab1:
                        pie_by_solution = px.pie(df, names="Transporteur", title="% du nombre total de livraisons prises en charges par livreur")
                        st.plotly_chart(pie_by_solution, use_container_width=True)
                    with tab2:
                        hist_by_solution = px.histogram(df, x="Transporteur", title="Nombre de livraisons prises en charges par livreur")
                        
                        st.plotly_chart(hist_by_solution, use_container_width=True)
                    
                
                with col2:
                    tab1, tab2 = st.tabs(["Hist.", " "])                    
                    with tab1:
                        bar_taux_delivered = px.bar(df_by_solution_delivered_taux, title="Taux de livraison par livreur")
                        bar_taux_delivered.update_layout(yaxis_range=[0, 100])
                        bar_taux_delivered.update_yaxes(title="%")
                        st.plotly_chart(bar_taux_delivered, use_container_width=True)

                col1, col2 = st.columns(2)
                
                with col1:
                    tab1, tab2 = st.tabs(["Pie chart", "Hist."])
                    with tab1:
                        pie_by_solution_delay= px.pie(df[(df["Status"] == "Livré") & (df["Retard"] == "oui")], names="Transporteur",
                                                      title="% du nombre total de livraisons en retard par livreur")
                        
                        st.plotly_chart(pie_by_solution_delay, use_container_width=True)
                    
                    with tab2:
                        hist_by_solution_delay = px.histogram(df[(df["Status"] == "Livré") & (df["Retard"] == "oui")], x="Transporteur",
                                                            title="Nombre de livraisons en retard par livreur")
                        st.plotly_chart(hist_by_solution_delay, use_container_width=True)
                
                with col2:
                    tab1, tab2 = st.tabs(["Hist.", " "])
                    with tab1:
                        bar_taux_delivered_delay = px.bar(df_by_solution_delivered_delay_taux, title="Taux de livraison en retard par livreur")
                        bar_taux_delivered_delay.update_layout(yaxis_range=[0, 100])
                        bar_taux_delivered_delay.update_yaxes(title="%")
                        st.plotly_chart(bar_taux_delivered_delay, use_container_width=True)
                
                col1, col2 = st.columns(2)
                
                with col1:        
                    tab1, tab2 = st.tabs(["Pie chart", "Hist."])
                    with tab1:
                        pie_by_solution_erreur = px.pie(df[(df["Status"] == "Livré") & (df["Erreur de colissage/Manque"] == "oui")], names="Transporteur",
                                                        title="% du nombre total de livraisons avec erreur colisage par livreur")
                        st.plotly_chart(pie_by_solution_erreur, use_container_width=True)
                    
                    with tab2:
                        hist_by_solution_erreur = px.histogram(df[(df["Status"] == "Livré") & (df["Erreur de colissage/Manque"] == "oui")], x="Transporteur",
                                                            title="Nombre de livraisons avec erreur colisage par livreur")
                        st.plotly_chart(hist_by_solution_erreur, use_container_width=True)
                
                with col2: 
                    tab1, tab2 = st.tabs(["Hist", " "])
                    with tab1:
                        bar_taux_delivered_erreur = px.bar(df_by_solution_delivered_erreur_taux, title="Taux de livraison avec erreur de colisage par livreur")
                        bar_taux_delivered_erreur.update_layout(yaxis_range=[0, 100])
                        bar_taux_delivered_erreur.update_yaxes(title="%")
                        st.plotly_chart(bar_taux_delivered_erreur, use_container_width=True)
                
            # stats by month
            with st.container():
                st.markdown("## Statistiques par mois")
                hist_by_month = px.histogram(df[df["Status"] == "Livré"], x="Mois livraison", title="Nombres de livraison (avec succès) par mois")
                st.plotly_chart(hist_by_month, use_container_width=True)