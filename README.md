# COVID_plots

## repository for parsing and visualization of Johns Hopkins CSSE COVID-19 data

### checkout the neccessary repositories
```
git clone git@github.com:CSSEGISandData/COVID-19.git && git clone git@github.com:yetyetanotherusername/COVID_plots.git
```

### create python environment & install dependencies
```
cd COVID_plots
python3 -m venv .env
source .env/bin/activate
pip install -Ur requirements.txt
```

### run script
```
python COVID_plots/data_exploration.py
```

### animated map plot
```
bokeh serve --show COVID_plots/map.py
```

plots can be found in `COVID_plots/figures`