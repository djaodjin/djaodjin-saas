(function ($) {

   function State(el, options){
      this.element = $(el);
      this.options = options;
      this._init();
   }

   State.prototype = {
      _init: function () {
          var stateSel = this;
          var coutrySel = $(this.options.country);
          coutrySel.change(function() {
              stateSel._country(this.value);
          });
      },

      _country: function (country) {
          var node = this.element;
          var stateSel = '';
          if( country in this._states ) {
              stateSel = '<select id="id_state" name="state">';
              var localStates = this._states[country];
              for(var key in localStates ) {
                  stateSel += '<option value="' + key + '">'
                      + localStates[key] + '</option>';
              }
              stateSel += '</select>';
          } else {
              stateSel = '<input id="id_state" name="state" type="text">'
          }
          stateSel = $(stateSel);
          this.element.replaceWith(stateSel);
          this.element = stateSel;
      },

      _states: {
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

   $.fn.state = function(options) {
      var opts = $.extend( {}, $.fn.state.defaults, options );
      state = new State($(this), opts);
   };

   $.fn.state.defaults = {
      country: null,
   };

})(jQuery);
