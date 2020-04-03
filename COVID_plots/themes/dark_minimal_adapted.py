text_font = 'Computer Modern'

json = {
    'attrs': {
        'Figure': {
            'background_fill_color': '#20262B',
            'border_fill_color': '#15191C',
            'outline_line_color': '#E0E0E0',
            'outline_line_alpha': 0.25,

            'aspect_ratio': 2,
            'sizing_mode': 'scale_both',
        },

        'Grid': {
            'grid_line_color': '#E0E0E0',
            'grid_line_alpha': 0.25
        },

        'Axis': {
            'major_tick_line_alpha': 0,
            'major_tick_line_color': '#E0E0E0',

            'minor_tick_line_alpha': 0.25,
            'minor_tick_line_color': '#E0E0E0',

            'axis_line_alpha': 0,
            'axis_line_color': '#E0E0E0',

            'major_label_text_color': '#E0E0E0',
            'major_label_text_font': text_font,
            'major_label_text_font_size': '1em',

            'axis_label_standoff': 10,
            'axis_label_text_color': '#E0E0E0',
            'axis_label_text_font': text_font,
            'axis_label_text_font_size': '1.2em',
            'axis_label_text_font_style': 'normal'
        },

        'Legend': {
            'spacing': 1,
            'glyph_width': 10,

            'label_standoff': 3,
            'label_text_color': '#E0E0E0',
            'label_text_font': text_font,
            'label_text_font_size': '1.2em',

            'border_line_alpha': 0,
            'background_fill_alpha': 0.25,
            'background_fill_color': '#20262B',

            'location': 'top_left',
            'click_policy': 'hide'
        },

        'ColorBar': {
            'title_text_color': '#E0E0E0',
            'title_text_font': text_font,
            'title_text_font_size': '1em',
            'title_text_font_style': 'normal',

            'major_label_text_color': '#E0E0E0',
            'major_label_text_font': text_font,
            'major_label_text_font_size': '1em',

            'background_fill_color': '#15191C',
            'major_tick_line_alpha': 0,
            'bar_line_alpha': 0
        },

        'Title': {
            'text_color': '#E0E0E0',
            'text_font': text_font,
            'text_font_size': '1.2em'
        },

        'Toolbar': {
            'active_scroll': None
        }
    }
}
