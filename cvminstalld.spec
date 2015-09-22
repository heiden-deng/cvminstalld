Name: cvminstalld
Version: 1.0.0
Release: 1
Summary: Sugon cvm install service server
URL: http://www.sugon.com/svn/cdn/trunk/cvminstalld/Revision_SVN_REVISION
Group: Sugon/Common
License: Commercial
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Source: cvminstalld-%{version}.tar.gz

%description
cvminstalld is http server for cvm install service.


%prep
%setup -q -n cvminstalld-%{version}

%build
echo 

%install

rm -rf %{buildroot}
mkdir -p %{buildroot}/etc/init.d
mkdir -p %{buildroot}/usr/sbin
mkdir -p %{buildroot}/var/templates
mkdir -p %{buildroot}/usr/lib64/python2.6/site-packages

install -m 555 init.d/cvminstalld %{buildroot}/etc/init.d/cvminstalld
install -m 555 usr/sbin/cvminstalld %{buildroot}/usr/sbin/cvminstalld
install -m 555 vcell_iutils.py %{buildroot}/usr/lib64/python2.6/site-packages/vcell_iutils.py
cp templates/*.html %{buildroot}/var/templates


%clean
[ "%{buildroot}" != "/" ] && %{__rm} -rf %{buildroot}


%files
%defattr(-,root,root)
/usr/sbin/*
/etc/init.d/*
/var/templates/*.html
/usr/lib64/python2.6/site-packages/*


%changelog
* Tue Sep 22 2015 heiden deng <dengjq@sugon.com>
- create
