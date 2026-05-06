import google.generativeai as genai
genai.configure(api_key="AIzaSyC8Sff-dubqwO2bj-PCohSdVqRvEVFqq4g")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
