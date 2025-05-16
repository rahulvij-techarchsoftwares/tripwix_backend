document.addEventListener("DOMContentLoaded", function() {
    let countrySelect = document.getElementById("id_country");
    let citySelect = document.getElementById("id_city");
    let locationSelect = document.getElementById("id_location");
    let subLocationSelect = document.getElementById("id_sublocation");
    const originalCountry = countrySelect.value;
    const originalCity = citySelect.value;
    const originalLocation = locationSelect.value;
    const originalSubLocation = subLocationSelect.value;

    function resetCountryOptions() {
        countrySelect.selectedIndex = 0;
    }

    function resetCityOptions() {
        citySelect.innerHTML = "";
        let cityDefaultOption = document.createElement("option");
        cityDefaultOption.value = "";
        cityDefaultOption.text = "---------";
        citySelect.appendChild(cityDefaultOption);
    }

    function resetLocationOptions() {
        locationSelect.innerHTML = "";
        let locationDefaultOption = document.createElement("option");
        locationDefaultOption.value = "";
        locationDefaultOption.text = "---------";
        locationSelect.appendChild(locationDefaultOption);
    }

    function resetSubLocationOptions() {
        subLocationSelect.innerHTML = "";
        let subLocationDefaultOption = document.createElement("option");
        subLocationDefaultOption.value = "";
        subLocationDefaultOption.text = "---------";
        subLocationSelect.appendChild(subLocationDefaultOption);
    }

    async function filterCitiesByCountry(selectedCountry) {
        return new Promise((resolve, reject) => {
            let xhr = new XMLHttpRequest();
            let url = "/city_options/?country=" + selectedCountry;
            xhr.open("GET", url, true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        let cityOptions = JSON.parse(xhr.responseText);
                        cityOptions.forEach(function(cityOption) {
                            let option = document.createElement("option");
                            option.value = cityOption.id;
                            option.text = cityOption.name;
                            citySelect.appendChild(option);
                        });
                        resolve();
                    } else {
                        reject(new Error("Failed to load cities"));
                    }
                }
            };
            xhr.send();
        });
    }

    async function filterLocationsByCountry(selectedCountry) {
        return new Promise((resolve, reject) => {
            let xhr = new XMLHttpRequest();
            let url = "/destination_options/?country=" + selectedCountry;
            xhr.open("GET", url, true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        let destinationOptions = JSON.parse(xhr.responseText);
                        destinationOptions.forEach(function(destinationOption) {
                            let option = document.createElement("option");
                            option.value = destinationOption.id;
                            option.text = destinationOption.name;
                            locationSelect.appendChild(option);
                        });
                        resolve();
                    } else {
                        reject(new Error("Failed to load locations"));
                    }
                }
            };
            xhr.send();
        });
    }

    async function filterLocationsByCity(selectedCity) {
        return new Promise((resolve, reject) => {
            let xhr = new XMLHttpRequest();
            let url = "/destination_options/?city=" + selectedCity;
            xhr.open("GET", url, true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        let destinationOptions = JSON.parse(xhr.responseText);
                        destinationOptions.forEach(function(destinationOption) {
                            let option = document.createElement("option");
                            option.value = destinationOption.id;
                            option.text = destinationOption.name;
                            locationSelect.appendChild(option);
                        });
                        resolve();
                    } else {
                        reject(new Error("Failed to load locations"));
                    }
                }
            };
            xhr.send();
        });
    }

    async function filterSubLocationsByLocation(selectedLocation) {
        return new Promise((resolve, reject) => {
            let xhr = new XMLHttpRequest();
            let url = "/community_options/?destination=" + selectedLocation;
            xhr.open("GET", url, true);
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4) {
                    if (xhr.status === 200) {
                        let communityOptions = JSON.parse(xhr.responseText);
                        communityOptions.forEach(function(communityOption) {
                            let option = document.createElement("option");
                            option.value = communityOption.id;
                            option.text = communityOption.name;
                            subLocationSelect.appendChild(option);
                        });
                        resolve();
                    } else {
                        reject(new Error("Failed to load sublocations"));
                    }
                }
            };
            xhr.send();
        });
    }

    function setInitialCity() {
        let cityOptions = citySelect.options;
        for (let i = 0; i < cityOptions.length; i++) {
            if (cityOptions[i].value == originalCity) {
                cityOptions[i].selected = true;
                break;
            }
        }
    }

    function setInitialLocation() {
        let locationOptions = locationSelect.options;
        for (let i = 0; i < locationOptions.length; i++) {
            if (locationOptions[i].value === originalLocation) {
                locationOptions[i].selected = true;
                break;
            }
        }
    }

    function setInitialSubLocation() {
        let subLocationOptions = subLocationSelect.options;
        for (let i = 0; i < subLocationOptions.length; i++) {
            if (subLocationOptions[i].value === originalSubLocation) {
                subLocationOptions[i].selected = true;
                break;
            }
        }
    }

    async function filterInitialData(originalCountry, originalLocation) {
        if (!originalCountry) {
            resetCityOptions();
            resetLocationOptions();
            resetSubLocationOptions();
            return;
        }

        resetLocationOptions();
        resetSubLocationOptions();
        resetCityOptions();

        try {
            await Promise.all([
                filterCitiesByCountry(originalCountry),
                filterLocationsByCountry(originalCountry),
            ]);

            // Give DOM time to update
            await new Promise((resolve) => setTimeout(resolve, 100));

            if (originalLocation) {
                // setInitialLocation();
                await filterSubLocationsByLocation(originalLocation);

                resetCountryOptions();

                // Give DOM time to update
                await new Promise((resolve) => setTimeout(resolve, 100));

                if (originalSubLocation) {
                    setInitialSubLocation();
                }
            }
        } catch (error) {
            console.error("Error loading initial data:", error);
        }
    }

    function updateCitiesByCountryOptions(selectedCountry) {
        if (!citySelect.value || selectedCountry !== originalCountry) {
            resetCityOptions();
            filterCitiesByCountry(selectedCountry).then(() => {
                console.log("Filtered cities by country");
            });
        }
    }

    function updateDestinationByCountryOptions(selectedCountry) {
        if (!locationSelect.value || selectedCountry !== originalCountry) {
            resetLocationOptions();
            resetSubLocationOptions();
            filterLocationsByCountry(selectedCountry).then(() => {
                console.log("Filtered locations by country");
            });
        }
    }

    function handleCountryChange() {
        let selectedCountry = countrySelect.value;
        updateCitiesByCountryOptions(selectedCountry);
        updateDestinationByCountryOptions(selectedCountry);
    }

    function updateDestinationByCityOptions(selectedCity) {
        if (
            !locationSelect.value ||
            !citySelect.value ||
            selectedCity !== originalCity
        ) {
            resetLocationOptions();
            resetSubLocationOptions();
            filterLocationsByCity(selectedCity).then(() => {
                console.log("Filtered locations by city");
            });
        }
    }

    function handleCityChange() {
        let selectedCity = citySelect.value;
        updateDestinationByCityOptions(selectedCity);
    }

    function updateSubLocationOptions(selectedLocation) {
        if (
            !locationSelect.value ||
            !subLocationSelect.value ||
            selectedLocation !== originalLocation
        ) {
            resetSubLocationOptions();
            filterSubLocationsByLocation(selectedLocation).then(() => {
                console.log("Filtered sublocations by location");
            });
        }
    }

    function handleLocationChange() {
        let selectedLocation = locationSelect.value;
        updateSubLocationOptions(selectedLocation);
    }

    filterInitialData(originalCountry, originalLocation).then(() => {
        if (originalCity) {
            setInitialCity();
        }

        if (originalLocation) {
            setInitialLocation();
        }

        if (originalSubLocation) {
            setInitialSubLocation();
        }
    });

    countrySelect.addEventListener("change", handleCountryChange);
    citySelect.addEventListener("change", handleCityChange);
    locationSelect.addEventListener("change", handleLocationChange);
});
