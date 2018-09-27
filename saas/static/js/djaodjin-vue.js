$.ajaxSetup({ cache: false });

Vue.mixin({
    delimiters: ['[[',']]'],
});

Vue.use(uiv, {prefix: 'uiv'});

Vue.filter('formatDate', function(value, format) {
  if (value) {
    if(!format){
        format = 'MM/DD/YYYY hh:mm'
    }
    return moment(String(value)).format(format)
  }
});

Vue.filter('currencyToSymbol', function(currency) {
    if( currency === "usd" || currency === "cad" ) { return "$"; }
    else if( currency === "eur" ) { return "\u20ac"; }
    return currency;
});

Vue.filter('humanizeCell', function(cell, unit, scale) {
    var currencyFilter = Vue.filter('currency');
    var currencyToSymbolFilter = Vue.filter('currencyToSymbol');
    scale = scale || 1;
    var value = cell * scale;
    var symbol = '';
    if(unit) {
        symbol = currencyToSymbolFilter(unit);
    }
    return currencyFilter(value, symbol, 2);
});

Vue.component('user-typeahead', {
    template: "",
    data: function(){
        return {
            url: djaodjinSettings.urls.api_users,
            searching: false,
            // used in a http request
            typeaheadQuery: '',
            // used to hold the selected item
            itemSelected: '',
        }
    },
    computed: {
        params: function(){
            res = {}
            if(this.typeaheadQuery) res.q = this.typeaheadQuery;
            return res
        },
    },
    methods: {
        // called by typeahead when a user enters input
        getUsers: function(query, done) {
            var vm = this;
            vm.searching = true;
            vm.typeaheadQuery = query;
            $.get(vm.url, vm.params, function(res){
                vm.searching = false;
                done(res.results)
            });
        },
        submit: function(){
            this.$emit('item-save', this.itemSelected);
            this.itemSelected = '';
        }
    },
});

if($('#coupon-list-container').length > 0){
var app = new Vue({
    el: "#coupon-list-container",
    components: {
        paginate: VuejsPaginate
    },
    data: {
        currentPage: 1,
        itemsPerPage: djaodjinSettings.itemsPerPage,
        filterExpr: "",
        couponsLoaded: false,
        dir: {
            code: "asc"
        },
        o: "code",
        ot: null,
        q: "",
        coupons: {
            results:[],
            count: 0
        },
        newCoupon: {
            code: '',
            percent: ''
        },
        edit_description: [],
        date: null
    },
    computed: {
        params: function(){
            res = {o: this.o}
            if(this.ot){
                res.ot = this.ot
            } else {
                res.ot = this.dir.code
            }
            if(this.currentPage > 1) res.page = this.currentPage;
            if(this.q) res.q = this.q;
            return res
        },
        totalItems: function(){
            return this.coupons.count
        },
        pageCount: function(){
            return Math.ceil(this.totalItems / this.itemsPerPage)
        }
    },
    methods: {
        get: function(){
            var vm = this;
            $.get(djaodjinSettings.urls.saas_api_coupon_url, vm.params, function(res){
                vm.coupons = res
                vm.couponsLoaded = true;
            })
        },
        remove: function(idx){
            var vm = this;
            var code = this.coupons.results[idx].code;
            $.ajax({
                method: 'DELETE',
                url: djaodjinSettings.urls.saas_api_coupon_url + '/' + code,
            }).done(function() {
                vm.get()
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        update: function(coupon){
            var vm = this;
            $.ajax({
                method: 'PUT',
                url: djaodjinSettings.urls.saas_api_coupon_url + '/' + coupon.code,
                data: coupon,
            }).done(function (resp) {
                vm.get()
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        save: function(){
            var vm = this;
            $.ajax({
                method: 'POST',
                url: djaodjinSettings.urls.saas_api_coupon_url,
                data: vm.newCoupon,
            }).done(function (resp) {
                vm.get()
                vm.newCoupon = {
                    code: '',
                    percent: ''
                }
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        editDescription: function(idx){
            var vm = this;
            vm.edit_description = Array.apply(
                null, new Array(vm.coupons.results.length)).map(function() {
                return false;
            });
            vm.$set(vm.edit_description, idx, true)
            // at this point the input is rendered and visible
            vm.$nextTick(function(){
                vm.$refs.edit_description_input[idx].focus();
            });
        },
        saveDescription: function(coupon, idx, event){
            if (event.which === 13 || event.type === "blur" ){
                this.$set(this.edit_description, idx, false)
                this.update(this.coupons.results[idx])
            }
        },
        selected: function(idx){
            var coupon = this.coupons.results[idx]
            coupon.ends_at = (new Date(coupon.ends_at)).toISOString()
            this.update(coupon)
        },
        filterList: function(){
            if(this.filterExpr) {
                if ("page" in this.params){
                    this.currentPage = 1;
                }
                this.q = this.filterExpr;
            } else {
                this.q = null;
            }
            this.couponsLoaded = false;
            this.get()
        },
        sortBy: function(fieldName) {
            if(this.dir[fieldName] === "asc" ) {
                this.dir = {};
                this.dir[fieldName] = "desc";
            } else {
                this.dir = {};
                this.dir[fieldName] = "asc";
            }
            this.o = fieldName;
            this.ot = this.dir[fieldName];
            this.currentPage = 1;
            this.get()
        }
    },
    mounted: function(){
        this.get()
    }
})
}

var itemListMixin = {
    components: {
        paginate: VuejsPaginate
    },
    data: function(){
        data = {
            filterExpr: '',
            o: djaodjinSettings.sortByField,
            ot: djaodjinSettings.sortDirection || "desc",
            q: '',
            currentPage: 1,
            itemsLoaded: false,
            itemsPerPage: djaodjinSettings.itemsPerPage,
            items: {
                results: [],
                count: 0
            },
            url: djaodjinSettings.urls.api_accounts
        }

        if(djaodjinSettings.date_range.ends_at ) {
            data['ends_at'] = moment(settings.date_range.ends_at).toDate()
        }
        return data
    },
    computed: {
        params: function(){
            res = {o: this.o}
            if(this.ot){
                res.ot = this.ot
            }
            if(this.currentPage > 1) res.page = this.currentPage;
            if(this.q) res.q = this.q;
            return res
        },
        totalItems: function(){
            return this.items.count
        },
        pageCount: function(){
            return Math.ceil(this.totalItems / this.itemsPerPage)
        }
    },
    methods: {
        get: function(){
            var vm = this;
            $.get(vm.url, vm.params, function(res){
                vm.items = res
                vm.itemsLoaded = true;
            });
        },
        filterList: function(){
            if(this.filterExpr) {
                if ("page" in this.params){
                    this.currentPage = 1;
                }
                this.q = this.filterExpr;
            } else {
                this.q = null;
            }
            this.itemsLoaded = false;
            this.get();
        },
        relativeDate: function(at_time) {
            var cutOff = new Date();
            if(this.ends_at ) {
                cutOff = new Date(this.ends_at);
            }
            var dateTime = new Date(at_time);
            if( dateTime <= cutOff ) {
                return moment.duration(cutOff - dateTime).humanize() + " ago";
            } else {
                return moment.duration(dateTime - cutOff).humanize() + " left";
            }
        }
    }
}



if($('#search-list-container').length > 0){
var app = new Vue({
    el: "#search-list-container",
    mixins: [itemListMixin],
})
}

if($('#today-sales-container').length > 0){
var app = new Vue({
    el: "#today-sales-container",
    mixins: [itemListMixin],
    data: {
        o: 'created_at',
        ot: "desc",
        url: djaodjinSettings.urls.api_receivables
    },
    mounted: function(){
        this.get()
    }
})
}

if($('#user-list-container').length > 0){
var app = new Vue({
    el: "#user-list-container",
    mixins: [itemListMixin],
    data: {
        o: 'created_at',
        ot: "desc",
    },
    mounted: function(){
        this.get()
    }
})
}

var userRelationMixin = {
    components: {
        paginate: VuejsPaginate
    },
    mixins: [itemListMixin],
    data: function(){
        return {
            url: djaodjinSettings.urls.saas_api_user_roles_url,
            modalOpen: false,
            unregistered: {
                slug: '',
                email: '',
                full_name: ''
            },
        }
    },
    methods: {
        get: function(){
            var vm = this;
            $.get(vm.url, vm.params, function(res){
                vm.items = res
                vm.itemsLoaded = true;
            });
        },
        remove: function(idx){
            var vm = this;
            var slug = this.items.results[idx].user.slug;
            if( djaodjinSettings.user && djaodjinSettings.user.slug === slug ) {
                if( !confirm("You are about to delete yourself from this" +
                             " role. it's possible that you no longer can manage" +
                             " this organization after performing this " +
                             " action.\n\nDo you want to remove yourself " +
                             " from this organization?") ) {
                    return;
                }
            }
            var url = vm.url + '/' + encodeURIComponent(slug);
            $.ajax({
                method: 'DELETE',
                url: url,
            }).done(function() {
                // splicing instead of refetching because
                // subsequent fetch might fail due to 403
                vm.items.results.splice(idx, 1);
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        saveUserRelation: function(slug){
            var vm = this;
            $.ajax({
                method: 'POST',
                url: vm.url,
                data: {slug: slug},
            }).done(function (resp) {
                vm.get()
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        handleNewUser: function(str){
            if(str.length > 0){
                this.unregistered = {
                    slug: str,
                    email: str,
                    full_name: str
                }
                this.modalOpen = true;
            }
        },
        save: function(item){
            if(item.slug !== undefined){
                this.saveUserRelation(item.slug)
            }
            else {
                this.handleNewUser(item)
            }
        },
        create: function(){
            var vm = this;
            var data = Object.assign({
                message: vm.$refs.modalText.value
            }, vm.unregistered)

            $.ajax({
                method: 'POST',
                url: vm.url + "?force=1",
                data: data,
            }).done(function (resp) {
                vm.modalOpen = false;
                vm.get()
            }).fail(function(resp){
                vm.modalOpen = false;
                showErrorMessages(resp);
            });
        }
    },
}

if($('#user-relation-list-container').length > 0){
var app = new Vue({
    el: "#user-relation-list-container",
    mixins: [userRelationMixin],
    methods: {
    },
    mounted: function(){
        this.get()
        var vm = this;
        vm.$on('form-submit', function(){
            vm.$refs.modalForm.submit()
        })
    }
})
}
