# CompanyHouse

## Scripts
 `monthly_sort.py` -- Sorts all the lenders according to the months in each year

 `get_directors.py`  -- Extracts the directors information from the 5.2m companies list. You can run the project using `python3 get_directors.py <keyn>`
 keyn - The api key index to use, Please refer to the documentation in the script to futher understand how it works, but the keyn is a number between `0` and `29`. Also , you can run the script by building a docker image and running a contianer out of the image.
 ### Creating the docker image
```
    docker build -t get_directors:v1 .
```
### Running container
```
    docker run --restart always -d --name get_directors<keyn> get_directors:v1 python3 /app/CompanyHouse/get_directors.py <keyn>
```


### TODO
    - Implement extracting the title number from the description text, maybe using regex 'title number <actual title number>'
    - Update the charges with the new title number and address
    - Update the company charges with the new charges