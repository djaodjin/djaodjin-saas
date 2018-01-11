(function ($) {
  "use strict";

   function Region(el, options){
      this.element = $(el);
      this.options = options;
      this.init();
   }

   Region.prototype = {
      init: function () {
          var self = this;
          var coutrySel = self.options.country ? $(self.options.country)
              : self.element.parents("form").find("[name='country']");
          coutrySel.change(function() {
              self._country(this.value);
          });
          self._country(coutrySel.val());
      },

      _country: function (country) {
          var self = this;
          var node = self.element;
          var id = self.element.attr("id");
          var name = self.element.attr("name");
          var value = self.element.val();
          var regionSel = "";
          if( country in self._regions ) {
              regionSel = "<select id=\"" + id +
              "\" class=\"form-control\" name=\"" + name + "\">";
              var localRegions = self._regions[country];
              for(var key in localRegions ) {
                  regionSel += "<option value=\"" + key + "\"";
                  if(key === value) {
                      regionSel += "selected";
                  }
                  regionSel += ">" + localRegions[key] + "</option>";
              }
              regionSel += "</select>";
          } else if( !self.element.is("input") ) {
              regionSel = "<input id=\"" + id +
                "\" class=\"form-control\" name=\"" + name +
                "\" type=\"text\" value=\"\">";
          }
          if( regionSel ) {
              regionSel = $(regionSel);
              self.element.replaceWith(regionSel);
              self.element = regionSel;
          }
      },

      _regions: {
"CA": {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NT": "Northwest Territories",
    "NS": "Nova Scotia",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon"},
"US": {
    "AL": "Alabama",
    "AK": "Alaska",
    "AS": "American Samoa",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "AA": "Armed Forces Americas",
    "AE": "Armed Forces Europe",
    "AP": "Armed Forces Pacific",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FM": "Federated States of Micronesia",
    "FL": "Florida",
    "GA": "Georgia",
    "GU": "Guam",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MH": "Marshall Islands",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "MP": "Northern Mariana Islands",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PW": "Palau",
    "PA": "Pennsylvania",
    "PR": "Puerto Rico",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VI": "Virgin Islands",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming"}
      }

   };

   $.fn.region = function(options) {
      var opts = $.extend( {}, $.fn.region.defaults, options );
      return new Region($(this), opts);
   };

   $.fn.region.defaults = {
      country: null
   };

   $(document).ready(function(){
      $("[name='region']").region();
   });

})(jQuery);
