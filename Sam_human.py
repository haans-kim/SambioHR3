import pandas as pd
import pickle
import time

# Measure the time it takes to load the Excel file
start_time = time.time()
df = pd.read_excel('data/tag_data_24.6.xlsx')
excel_load_time = time.time() - start_time
print(f"Time to load Excel file: {excel_load_time:.2f} seconds")

# Save the DataFrame to a pickle file
with open('tag_data.pkl', 'wb') as f:
    pickle.dump(df, f)

# Measure the time it takes to load the pickle file
start_time = time.time()
with open('tag_data.pkl', 'rb') as f:
    loaded_df = pickle.load(f)
pickle_load_time = time.time() - start_time
print(f"Time to load pickle file: {pickle_load_time:.2f} seconds")

# Print the loaded DataFrame
print(loaded_df)

