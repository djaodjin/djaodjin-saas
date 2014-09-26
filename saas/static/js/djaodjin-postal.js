(function ($) {

   function Region(el, options){
      this.element = $(el);
      this.options = options;
      this._init();
   }

   Region.prototype = {
      _init: function () {
          var regionSel = this;
          var coutrySel = $(this.options.country);
          coutrySel.change(function() {
              regionSel._country(this.value);
          });
      },

      _country: function (country) {
          var node = this.element;
          var id = this.element.attr('id');
          var name = this.element.attr('name');
          var value = this.element.val();
          var regionSel = '';
          if( country in this._regions ) {
              regionSel = '<select id="' + id
                  + '" class="form-control" name="' + name + '">';
              var localRegions = this._regions[country];
              for(var key in localRegions ) {
                  regionSel += '<option value="' + key + '"';
                  if(key == value) {
                      regionSel += 'selected';
                  }
                  regionSel += '>' + localRegions[key] + '</option>';
              }
              regionSel += '</select>';
          } else {
              regionSel = '<input id="' + id
                  + '" class="form-control" name="' + name
                  + '" type="text" value="' + value + '">'
          }
          regionSel = $(regionSel);
          this.element.replaceWith(regionSel);
          this.element = regionSel;
      },

      _regions: {
"US": {
    'AL': 'Alabama',
    'AK': 'Alaska',
    'AS': 'American Samoa',
    'AZ': 'Arizona',
    'AR': 'Arkansas',
    'AA': 'Armed Forces Americas',
    'AE': 'Armed Forces Europe',
    'AP': 'Armed Forces Pacific',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DE': 'Delaware',
    'DC': 'District of Columbia',
    'FM': 'Federated States of Micronesia',
    'FL': 'Florida',
    'GA': 'Georgia',
    'GU': 'Guam',
    'HI': 'Hawaii',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'IA': 'Iowa',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'ME': 'Maine',
    'MH': 'Marshall Islands',
    'MD': 'Maryland',
    'MA': 'Massachusetts',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MS': 'Mississippi',
    'MO': 'Missouri',
    'MT': 'Montana',
    'NE': 'Nebraska',
    'NV': 'Nevada',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NY': 'New York',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'MP': 'Northern Mariana Islands',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PW': 'Palau',
    'PA': 'Pennsylvania',
    'PR': 'Puerto Rico',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VT': 'Vermont',
    'VI': 'Virgin Islands',
    'VA': 'Virginia',
    'WA': 'Washington',
    'WV': 'West Virginia',
    'WI': 'Wisconsin',
    'WY': 'Wyoming'},
      },

   }

   $.fn.region = function(options) {
      var opts = $.extend( {}, $.fn.region.defaults, options );
      region = new Region($(this), opts);
   };

   $.fn.region.defaults = {
      country: null,
   };

})(jQuery);
