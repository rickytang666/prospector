
sources.json (list of pages to scrape) 
-> gather.py (scrapes list pages and use LLM to extract company names and URLs) 
used yc api (capped at 5 pages), velocity bs4 (91 extracted), llm inferring links for design team links (w/ no href)
-> scrape.py (scrapes individual pages) 
for yc/velocity we use internal info and then visit company website to smart crawl
for other companies from design team sources we smart crawl but make a note of the source
-> enrich.py (uses LLM to extract structured info from scraped pages)

output
