import pandas as pd
import matplotlib.pyplot as plt

def profile_categories(total_means, category_means, category_ordering, ax, bounds=(0,1)):
    all_means = pd.concat([category_means.T, pd.Series(total_means, name='Total')], axis=1)
    all_means = all_means[all_means['Total'].between(bounds[0], bounds[1])].sort_values('Total')

    over_idx = 120
    under_idx = 80
    for idx, cat in enumerate(all_means[category_ordering]):
        indices_to_total = 100*all_means[cat]/all_means['Total']
        color_code = -1 * (indices_to_total < under_idx) + (indices_to_total > over_idx)
        colors = color_code.map({-1: 'r', 0: 'k', 1: 'g'})
        ax[idx] = all_means[cat].plot(kind='barh', ax=ax[idx], color=''.join(list(colors)), title=cat)
        ax[idx].set_xlim(0,1) 
        if idx > 0:
            ax[idx].set_yticklabels([])
    