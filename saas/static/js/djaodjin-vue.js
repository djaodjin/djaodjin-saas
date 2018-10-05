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
    if(!(value instanceof Date)){
        value = String(value);
    }
    return moment(value).format(format)
  }
});

Vue.filter("monthHeading", function(d) {
    // shift each period by 1 month unless this is
    // current month and not a first day of the month
    if( typeof d === 'string' ) {
        d = moment(d);
    }
    if(d.date() !== 1 || d.hour() !== 0
       || d.minute() !== 0 || d.second() !== 0 ) {
        return d.format("MMM'YY*");
    }
    return d.clone().subtract(1, 'months').format("MMM'YY");
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

Vue.filter('relativeDate', function(at_time) {
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
            if(!vm.url) {
                done([]);
            }
            else {
                vm.searching = true;
                vm.typeaheadQuery = query;
                $.get(vm.url, vm.params, function(res){
                    vm.searching = false;
                    done(res.results)
                });
            }
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
            data['ends_at'] = moment(djaodjinSettings.date_range.ends_at).toDate()
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
    mounted: function(){
        this.get()
    }
})
}

if($('#metrics-container').length > 0){
var app = new Vue({
    el: "#metrics-container",
    mixins: [],
    data: function(){
        var data = {
            tables: djaodjinSettings.tables,
            currentTab: 0,
            timezone: 'local',
            tableData: {},
        }
        var ends_at = moment(djaodjinSettings.date_range.ends_at);
        if(ends_at.isValid()){
            data.ends_at = ends_at.toDate();
        }
        else {
            data.ends_at = moment().toDate();
        }
        return data;
    },
    methods: {
        fetchTableData: function(table, cb){
            var vm = this;
            var params = {"ends_at": moment(vm.ends_at).format()};
            if( vm.timezone !== 'utc' ) {
                params["timezone"] = moment.tz.guess();
            }
            $.get(table.location, params, function(resp){
                var unit = resp.unit;
                var scale = resp.scale;
                scale = parseFloat(scale);
                if( isNaN(scale) ) {
                    scale = 1.0;
                }
                // add "extra" rows at the end
                var extra = resp.extra || [];

                var tableData = {
                    unit: unit,
                    scale: scale,
                    data: resp.table
                }
                vm.convertDatetime(tableData.data, vm.timezone === 'utc');
                vm.$set(vm.tableData, table.key, tableData)

                if(cb) cb();
            });
        },
        convertDatetime: function(data, isUTC){
            // Convert datetime string to moment object in-place because we want
            // to keep extra keys and structure in the JSON returned by the API.
            return data.map(function(f){
                var values = f.values.map(function(v){
                    // localizing the period to local browser time
                    // unless showing reports in UTC.
                    v[0] = isUTC ? moment.parseZone(v[0]) : moment(v[0]);
                });
            });
        },
        endOfMonth: function(date) {
            return new Date(
                date.getFullYear(),
                date.getMonth() + 1,
                0
            );
        },
        prepareCurrentTabData: function(){
            var vm = this;
            var table = vm.currentTable;
            vm.fetchTableData(table, function(){
                var tableData = vm.currentTableData;
                 // manual binding - trigger updates to the graph
                if( table.key === "balances") {
                    // XXX Hard-coded.
                    updateBarChart("#metrics-chart-" + table.key,
                        tableData.data, tableData.unit, tableData.scale, tableData.extra);
                } else {
                    updateChart("#metrics-chart-" + table.key,
                        tableData.data, tableData.unit, tableData.scale, tableData.extra);
                }
            });
        },
        tabTitle: function(table){
            var filter = Vue.filter('currencyToSymbol');
            var unit = '';
            var tableData = this.tableData[table.key];
            if(tableData && tableData.unit){
                unit = ' (' + filter(tableData.unit) + ')';
            }
            return table.title + unit;
        },
    },
    computed: {
        currentTable: function(){
            return this.tables[this.currentTab];
        },
        currentTableData: function(){
            var res = {data: []}
            var key = this.currentTable.key;
            var data = this.tableData[key];
            if(data){
                res = data;
            }
            return res;
        },
        currentTableDates: function(){
            var res = [];
            var data = this.currentTableData.data;
            if(data && data.length > 0){
                res = data[0].values;
            }
            return res;
        }
    },
    mounted: function(){
        this.prepareCurrentTabData()
    }
})
}

var paginationMixin = {
    data: {
        currentPage: 1,
        itemsPerPage: djaodjinSettings.itemsPerPage,
    },
    computed: {
        totalItems: function(){
            return this.items.count
        },
        pageCount: function(){
            return Math.ceil(this.totalItems / this.itemsPerPage)
        }
    }
}

var filterableMixin = {
}

var sortableMixin = {
    data: function(){
        var res = {
            o: djaodjinSettings.sortByField || 'created_at',
            ot: djaodjinSettings.sortDirection || 'desc',
            dir: {},
        }
        res.dir[res.o] = res.ot;
        return res;
    },
    methods: {
        sortBy: function(fieldName) {
            var dir = {}
            if( this.dir[fieldName] === "asc" ) {
                dir[fieldName] = "desc";
            } else {
                dir[fieldName] = "asc";
            }
            this.dir = dir;
            this.o = fieldName;
            if(this.currentPage){
                this.currentPage = 1;
            }
            if(this.get){
                this.get();
            }
        }
    },
    computed: {
        params: function(){
            var res = {o: this.o, ot: this.dir[this.o]}
            if(this.currentPage > 1) res.page = this.currentPage;
            return res;
        }
    }
}

var subscriptionsMixin = {
    data: function(){
        var res = {
            o: 'created_at',
            dir: {},
        }
        res.dir[res.o] = 'desc';
        return res;
    },
    methods: {
        subscriptionURL: function(organization, plan) {
            return djaodjinSettings.urls.api_organizations
                + organization + "/subscriptions/" + plan;
        },
        endsSoon: function(subscription) {
            var cutOff = new Date(this.ends_at);
            cutOff.setDate(this.ends_at.getDate() + 5);
            var subEndsAt = new Date(subscription.ends_at);
            if( subEndsAt < cutOff ) {
                return "ends-soon";
            }
            return "";
        },
    },
    computed: {
        params: function(){
            var res = {o: this.o, ot: this.dir[this.o]}
            if(this.currentPage > 1) res.page = this.currentPage;
            return res;
        },
    },
}

if($('#subscribers-list-container').length > 0){
var app = new Vue({
    el: "#subscribers-list-container",
    mixins: [subscriptionsMixin],
    data: {
        currentTab: 1,
        currentPage: 1,
        itemsPerPage: djaodjinSettings.itemsPerPage,
        filterExpr: '',
        ends_at: moment().endOf("day").toDate(),
        registered: {
            url: djaodjinSettings.urls.api_registered,
            results: [],
            count: 0,
            loaded: false
        },
        subscribed: {
            url: djaodjinSettings.urls.saas_api_active_subscribers,
            results: [],
            count: 0,
            loaded: false
        },
        churned: {
            url: djaodjinSettings.urls.saas_api_churned,
            results: [],
            count: 0,
            loaded: false
        },
        edit_description: [],
    },
    methods: {
        get: function(){
            var vm = this;
            var queryset = vm[vm.currentQueryset];
            $.get(queryset.url, vm.params, function(resp){
                queryset.results = resp.results;
                queryset.count = resp.count;
                queryset.loaded = true;
                vm[vm.currentQueryset] = queryset;
            });
        },
        resolve: function (o, s){
            return s.split('.').reduce(function(a, b) {
                return a[b];
            }, o);
        },
        groupBy: function (list, groupBy) {
            var vm = this;
            var res = {};
            var keys = [];
            list.forEach(function(item){
                var value = vm.resolve(item, groupBy);
                keys.push(value);
                res[value] = res[value] || [];
                res[value].push(item);
            });
            var unique_keys = Array.from(new Set(keys));
            var ordered_res = [];
            unique_keys.forEach(function(key){
                ordered_res.push(res[key])
            });
            return ordered_res;
        },
        sortBy: function(fieldName) {
            var dir = {}
            if( this.dir[fieldName] === "asc" ) {
                dir[fieldName] = "desc";
            } else {
                dir[fieldName] = "asc";
            }
            this.dir = dir;
            this.o = fieldName;
            this.currentPage = 1;
            this.get();
        },
        filterList: function() {
            if( this.filterExpr ) {
                this.currentPage = 1;
                this.q = this.filterExpr;
            } else {
                this.q = null;
            }
            this.get();
        },
        clearFilters: function(){
            var o = 'created_at';
            var dir = {};
            dir[o] = 'desc';
            this.o = o;
            this.dir = dir;
            this.q = '';
            this.currentPage = 1;
            this.editDescription = [];
        },
        tabChanged: function(){
            this.clearFilters();
            this.get();
        },
        update: function(item){
            var vm = this;
            var url = vm.subscriptionURL(
                item.organization.slug, item.plan.slug);
            $.ajax({
                method: 'PATCH',
                url: url,
                data: {description: item.description},
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        refId: function(item, group){
            var ids = [item.organization.slug,
                item.plan.slug, group];
            return ids.join('_').replace(new RegExp('[-:]', 'g'), '');
        },
        editDescription: function(item, group){
            var vm = this;
            vm.$set(item, 'edit_description', true);
            // at this point the input is rendered and visible
            vm.$nextTick(function(){
                var ref = vm.refId(item, group);
                vm.$refs[ref][0].focus();
            });
        },
        saveDescription: function(item){
            // this solves a problem where user hits an enter
            // which saves the description and then once they
            // click somewhere this callback is triggered again
            // due to the fact that the input is blurred even
            // though it is hidden by that time
            if(!item.edit_description) return;
            this.$set(item, 'edit_description', false);
            delete item.edit_description;
            this.update(item)
        },
    },
    computed: {
        params: function(){
            var res = {o: this.o, ot: this.dir[this.o]}
            if(this.currentPage > 1) res.page = this.currentPage;
            if(this.filterExpr) res.q = this.filterExpr;
            return res;
        },
        totalItems: function(){
            return this[this.currentQueryset].count
        },
        pageCount: function(){
            return Math.ceil(this.totalItems / this.itemsPerPage)
        },
        currentQueryset: function(){
            var sets = ['registered', 'subscribed', 'churned']
            return sets[this.currentTab];
        }
    },
    mounted: function(){
        this.get();
    }
})
}

if($('#subscriptions-list-container').length > 0){
var app = new Vue({
    el: "#subscriptions-list-container",
    mixins: [subscriptionsMixin, paginationMixin],
    data: {
        url: djaodjinSettings.urls.saas_api_subscriptions,
        items: {
            results: [],
            count: 0
        },
        itemsLoaded: false,
        modalOpen: false,
        plan: {},
        toDelete: {
            plan: null,
            org: null
        },
    },
    methods: {
        get: function(){
            var vm = this;
            $.get(vm.url, vm.params, function(resp){
                vm.items = resp;
                vm.itemsLoaded = true;
            });
        },
        update: function(item){
            var vm = this;
            var url = vm.subscriptionURL(
                item.organization.slug, item.plan.slug);
            var data = {
                description: item.description,
                ends_at: item.ends_at
            };
            $.ajax({
                method: 'PATCH',
                url: url,
                data: data,
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        selected: function(idx){
            var item = this.items.results[idx];
            item.ends_at = (new Date(item.ends_at)).toISOString();
            this.update(item);
        },
        subscribersURL: function(provider, plan) {
            return djaodjinSettings.urls.api_organizations + provider + "/plans/" + plan + "/subscriptions/";
        },
        subscribe: function(org){
            var vm = this;
            var url = vm.subscribersURL(vm.plan.organization, vm.plan.slug);
            var data = {
                organization: {
                  slug: org
                }
            }
            $.ajax({
                method: 'POST',
                url: url,
                contentType: 'application/json',
                data: JSON.stringify(data),
            }).done(function (){
                vm.get();
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
        unsubscribeConfirm: function(org, plan) {
            this.toDelete = {
                org: org,
                plan: plan
            }
            this.modalOpen = true;
        },
        unsubscribe: function() {
            var vm = this;
            var data = vm.toDelete;
            if(!(data.org && data.plan)) return;
            var url = vm.subscriptionURL(data.org, data.plan);
            $.ajax({
                method: 'DELETE',
                url: url,
            }).done(function (){
                vm.get();
                vm.modalOpen = false;
            }).fail(function(resp){
                showErrorMessages(resp);
                vm.modalOpen = false;
            });
        },
        acceptRequest: function(organization, request_key) {
            var vm = this;
            var url = (djaodjinSettings.urls.api_organizations +
                organization + "/subscribers/accept/" + request_key + "/");
            $.ajax({
                method: 'PUT',
                url: url,
            }).done(function (){
                vm.get();
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        },
    },
    mounted: function(){
        this.get();
    }
})
}

if($('#import-transaction-container').length > 0){
var app = new Vue({
    el: "#import-transaction-container",
    data: {
        url: djaodjinSettings.urls.saas_api_subscriptions,
        created_at: moment().format("YYYY-MM-DD"),
        itemsLoaded: false,
        itemSelected: '',
        searching: false,
    },
    methods: {
        getSubscriptions: function(query, done) {
            var vm = this;
            vm.searching = true;
            $.get(vm.url, {q: query}, function(res){
                vm.searching = false;
                // current typeahead implementation does not
                // support dynamic keys that's why we are
                // creating them here
                res.results.forEach(function(e){
                    e.itemKey = e.organization.slug + ':' + e.plan.slug
                });
                done(res.results)
            });
        },
    },
});
}

if($('#coupon-users-container').length > 0){
var app = new Vue({
    el: "#coupon-users-container",
    mixins: [itemListMixin, sortableMixin],
    data: {
        o: 'created_at',
        ot: "desc",
        url: djaodjinSettings.urls.api_metrics_coupon_uses
    },
    mounted: function(){
        this.get()
    }
})
}

if($('#billing-statement-container').length > 0){
var app = new Vue({
    el: "#billing-statement-container",
    mixins: [itemListMixin, sortableMixin],
    data: function(){
        var res = {
            o: 'created_at',
            ot: "desc",
            url: djaodjinSettings.urls.api_transactions,
            last4: "N/A",
            exp_date: "N/A",
            bank_name: "N/A",
            balance_amount: "N/A",
            balanceUrl: null,
            balanceLoaded: false,
            modalOpen: false,

            // TODO this should be in itemsMixin
            starts_at: '',
            ends_at: ''
        }
        return res;
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
        }
    },
    methods: {
        getBalance: function() {
            var vm = this;
            if(!vm.balanceUrl) return;
            $.get(vm.balanceUrl, function(resp){
                if( resp.balance_amount ) {
                    vm.balance_amount = resp.balance_amount;
                }
                if( resp.balance_unit ) {
                    vm.balance_unit = resp.balance_unit;
                }
                if( resp.last4 ) {
                    vm.last4 = resp.last4;
                }
                if( resp.exp_date ) {
                    vm.exp_date = resp.exp_date;
                }
                if( resp.bank_name ) {
                    vm.bank_name = resp.bank_name;
                }
                vm.balanceLoaded = true;
            });
        },
        cancelBalance: function(){
            var vm = this;
            $.ajax({
                method: 'DELETE',
                url: djaodjinSettings.urls.api_cancel_balance_due,
            }).done(function() {
                vm.get();
                vm.getBalance();
            }).fail(function(resp){
                showErrorMessages(resp);
            });
        }
    },
    mounted: function(){
        // TODO this is a hack
        var cont = this.$refs.billing_container;
        if(cont && cont.dataset.apiUrl){
            this.balanceUrl = cont.dataset.apiUrl;
            this.getBalance();
        }
        this.get()
    }
})
}
